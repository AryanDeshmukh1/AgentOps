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
        self.pipelines_table = self.dynamodb.Table(os.getenv("DYNAMODB_PIPELINES_TABLE", "AgentOps-Pipelines"))
        self.decisions_table = self.dynamodb.Table(os.getenv("DYNAMODB_AGENT_DECISIONS_TABLE", "AgentOps-AgentDecisions"))
        self.approvals_table = self.dynamodb.Table(os.getenv("DYNAMODB_APPROVALS_TABLE", "AgentOps-Approvals"))
        logger.info(f"DynamoDB service initialized (region={region})")

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


_service = None


def get_dynamodb_service():
    global _service
    if _service is None:
        _service = DynamoDBService()
    return _service
