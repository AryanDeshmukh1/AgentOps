"""
DynamoDB service for persisting pipeline state and agent decisions.
"""
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from shared.logger import get_logger

logger = get_logger(__name__)


def _convert_floats(obj):
    if isinstance(obj, list):
        return [_convert_floats(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def _restore_decimals(obj):
    if isinstance(obj, list):
        return [_restore_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _restore_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    return obj


class DynamoDBService:
    def __init__(self):
        region = os.getenv("AWS_REGION", "ca-central-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.pipelines_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_PIPELINES_TABLE", "AgentOps-Pipelines")
        )
        self.decisions_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_AGENT_DECISIONS_TABLE", "AgentOps-AgentDecisions")
        )
        self.approvals_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_APPROVALS_TABLE", "AgentOps-Approvals")
        )
        self.approval_events_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_APPROVAL_EVENTS_TABLE", "AgentOps-ApprovalEvents")
        )
        self.deployments_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_DEPLOYMENTS_TABLE", "AgentOps-Deployments")
        )
        self.deployment_events_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_DEPLOYMENT_EVENTS_TABLE", "AgentOps-DeploymentEvents")
        )
        self.metrics_table = self.dynamodb.Table(
            os.getenv("DYNAMODB_METRICS_TABLE", "AgentOps-Metrics")
        )
        logger.info(f"DynamoDB service initialized (region={region})")

    # ---------- Pipelines ----------

    async def save_pipeline(self, pipeline_data):
        try:
            item = {
                "pipeline_id": pipeline_data["pipeline_id"],
                "created_at": pipeline_data["timestamp"],
                "repo": pipeline_data["repo"],
                "pr_number": pipeline_data["pr_number"],
                "pr_title": pipeline_data["pr_title"],
                "pr_author": pipeline_data["pr_author"],
                "head_sha": pipeline_data["head_sha"],
                "base_sha": pipeline_data["base_sha"],
                "files_changed": len(pipeline_data["files"]),
                "status": "running",
                "current_agent": "ReviewAgent",
            }
            self.pipelines_table.put_item(Item=_convert_floats(item))
            logger.info(f"Saved pipeline: {pipeline_data['pipeline_id']}")
            return True
        except ClientError as e:
            logger.error(f"Failed to save pipeline: {e}")
            return False

    async def update_pipeline_status(self, pipeline_id, created_at, updates):
        try:
            update_parts = []
            ev = {}
            en = {}
            for key, value in updates.items():
                update_parts.append(f"#{key} = :{key}")
                ev[f":{key}"] = _convert_floats(value)
                en[f"#{key}"] = key
            self.pipelines_table.update_item(
                Key={"pipeline_id": pipeline_id, "created_at": created_at},
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeValues=ev,
                ExpressionAttributeNames=en,
            )
            logger.info(f"Updated pipeline {pipeline_id}: {list(updates.keys())}")
            return True
        except ClientError as e:
            logger.error(f"Failed to update pipeline: {e}")
            return False

    # ---------- Agent Decisions ----------

    async def save_agent_decision(self, pipeline_id, agent_name, report):
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            agent_timestamp = f"{agent_name}#{timestamp}"
            item = {
                "pipeline_id": pipeline_id,
                "agent_timestamp": agent_timestamp,
                "agent_name": agent_name,
                "timestamp": timestamp,
                "report": _convert_floats(report),
            }
            self.decisions_table.put_item(Item=item)
            logger.info(f"Saved {agent_name} decision for {pipeline_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to save agent decision: {e}")
            return False

    # ---------- Approvals ----------

    async def save_approval_request(self, pipeline_id, risk_assessment, review_summary):
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            approval_id = f"approval_{pipeline_id}_{int(datetime.now().timestamp())}"
            item = {
                "pipeline_id": pipeline_id,
                "approval_id": approval_id,
                "created_at": timestamp,
                "risk_level": risk_assessment["risk_level"],
                "reason": risk_assessment["reason"],
                "critical_files": risk_assessment.get("critical_files", []),
                "review_summary": _convert_floats(review_summary),
                "status": "pending",
                "approved_by": None,
                "approved_at": None,
                "comment": None,
            }
            self.approvals_table.put_item(Item=item)
            logger.info(f"Created approval request {approval_id} for {pipeline_id}")
            return approval_id
        except ClientError as e:
            logger.error(f"Failed to save approval: {e}")
            return ""

    async def get_approval(self, pipeline_id, approval_id):
        try:
            result = self.approvals_table.get_item(
                Key={"pipeline_id": pipeline_id, "approval_id": approval_id}
            )
            item = result.get("Item")
            return _restore_decimals(item) if item else None
        except ClientError as e:
            logger.error(f"Failed to get approval: {e}")
            return None

    async def transition_approval(
        self,
        pipeline_id,
        approval_id,
        new_status,
        actor,
        comment="",
        expected_status="pending",
    ):
        """Atomic conditional update — prevents double-approval."""
        try:
            self.approvals_table.update_item(
                Key={"pipeline_id": pipeline_id, "approval_id": approval_id},
                UpdateExpression=(
                    "SET #status = :new, approved_by = :actor, "
                    "approved_at = :now, #cmt = :comment"
                ),
                ConditionExpression="#status = :expected",
                ExpressionAttributeNames={"#status": "status", "#cmt": "comment"},
                ExpressionAttributeValues={
                    ":new": new_status,
                    ":expected": expected_status,
                    ":actor": actor,
                    ":now": datetime.now(timezone.utc).isoformat(),
                    ":comment": comment,
                },
            )
            logger.info(
                f"Transitioned approval {approval_id}: {expected_status} -> {new_status} by {actor}"
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    f"Approval transition rejected (state mismatch): {approval_id}"
                )
                return False
            logger.error(f"Failed to transition approval: {e}")
            return False

    async def save_approval_event(self, event):
        try:
            self.approval_events_table.put_item(Item=_convert_floats(event))
            logger.info(
                f"Audit {event['approval_id']}: {event['from_state']} -> {event['to_state']} by {event['actor']}"
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to save approval event: {e}")
            return False

    async def list_approval_events(self, approval_id):
        try:
            from boto3.dynamodb.conditions import Key
            result = self.approval_events_table.query(
                KeyConditionExpression=Key("approval_id").eq(approval_id),
                ScanIndexForward=True,
            )
            return _restore_decimals(result.get("Items", []))
        except ClientError as e:
            logger.error(f"Failed to list approval events: {e}")
            return []

    async def list_pending_approvals(self):
        try:
            result = self.approvals_table.scan(
                FilterExpression="#status = :pending",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":pending": "pending"},
            )
            return _restore_decimals(result.get("Items", []))
        except ClientError as e:
            logger.error(f"Failed to list pending approvals: {e}")
            return []

    # ---------- Deployments (Day 13+) ----------

    async def save_deployment(self, pipeline_id, deployment_id, approval_id,
                               repo, pr_number, head_sha):
        try:
            item = {
                "pipeline_id": pipeline_id,
                "deployment_id": deployment_id,
                "approval_id": approval_id or "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "repo": repo,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "status": "pending",
                "blue_slot": None,
                "green_slot": None,
                "traffic_split": {"blue": 100, "green": 0},
                "last_updated_by": "DeployAgent",
            }
            self.deployments_table.put_item(Item=_convert_floats(item))
            logger.info(f"Saved deployment: {deployment_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to save deployment: {e}")
            return False

    async def get_deployment(self, pipeline_id, deployment_id):
        try:
            result = self.deployments_table.get_item(
                Key={"pipeline_id": pipeline_id, "deployment_id": deployment_id}
            )
            item = result.get("Item")
            return _restore_decimals(item) if item else None
        except ClientError as e:
            logger.error(f"Failed to get deployment: {e}")
            return None

    async def transition_deployment(self, pipeline_id, deployment_id, new_status,
                                     actor, comment="", expected_status="pending"):
        """Atomic conditional update — prevents invalid state transitions."""
        try:
            self.deployments_table.update_item(
                Key={"pipeline_id": pipeline_id, "deployment_id": deployment_id},
                UpdateExpression=(
                    "SET #status = :new, last_updated_at = :now, "
                    "last_updated_by = :actor, last_comment = :comment"
                ),
                ConditionExpression="#status = :expected",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":new": new_status,
                    ":expected": expected_status,
                    ":actor": actor,
                    ":now": datetime.now(timezone.utc).isoformat(),
                    ":comment": comment,
                },
            )
            logger.info(
                f"Transitioned deployment {deployment_id}: "
                f"{expected_status} -> {new_status} by {actor}"
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    f"Deployment transition rejected (state mismatch): {deployment_id}"
                )
                return False
            logger.error(f"Failed to transition deployment: {e}")
            return False


    async def update_deployment_traffic_split(self, pipeline_id, deployment_id,
                                               blue_percent, green_percent):
        """Update only the traffic_split field — non-state-machine update."""
        try:
            self.deployments_table.update_item(
                Key={"pipeline_id": pipeline_id, "deployment_id": deployment_id},
                UpdateExpression="SET traffic_split = :split, last_updated_at = :now",
                ExpressionAttributeValues={
                    ":split": {"blue": blue_percent, "green": green_percent},
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(
                f"Updated traffic split {deployment_id}: "
                f"blue={blue_percent}% green={green_percent}%"
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to update traffic split: {e}")
            return False
        
        
    async def save_deployment_event(self, event):
        try:
            self.deployment_events_table.put_item(Item=_convert_floats(event))
            logger.info(
                f"Deployment audit {event['deployment_id']}: "
                f"{event['from_state']} -> {event['to_state']} by {event['actor']}"
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to save deployment event: {e}")
            return False
    
    # ---------- Metrics (Day 17+) ----------

    async def save_metric_sample(self, sample):
        try:
            self.metrics_table.put_item(Item=_convert_floats(sample))
            return True
        except ClientError as e:
            logger.error(f"Failed to save metric sample: {e}")
            return False

    async def list_recent_metrics(self, deployment_id, limit=20):
        """Get most recent metric samples for a deployment, newest first."""
        try:
            from boto3.dynamodb.conditions import Key
            result = self.metrics_table.query(
                KeyConditionExpression=Key("deployment_id").eq(deployment_id),
                ScanIndexForward=False,  # newest first
                Limit=limit,
            )
            return _restore_decimals(result.get("Items", []))
        except ClientError as e:
            logger.error(f"Failed to list metrics: {e}")
            return []

    async def list_promoted_deployments(self):
        """Scan for all deployments in the 'promoted' state. Used by metric worker."""
        try:
            result = self.deployments_table.scan(
                FilterExpression="#status = :promoted",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":promoted": "promoted"},
            )
            return _restore_decimals(result.get("Items", []))
        except ClientError as e:
            logger.error(f"Failed to list promoted deployments: {e}")
            return []
_service = None


def get_dynamodb_service():
    global _service
    if _service is None:
        _service = DynamoDBService()
    return _service