"""
DynamoDB service for persisting pipeline state and agent decisions.
Each pipeline gets saved so we can later display history in the dashboard.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from shared.logger import get_logger

logger = get_logger(__name__)


def _convert_floats(obj):
    """DynamoDB doesn't accept floats — convert to Decimal."""
    if isinstance(obj, list):
        return [_convert_floats(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def _restore_decimals(obj):
    """Convert Decimal back to float/int for JSON serialization."""
    if isinstance(obj, list):
        return [_restore_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _restore_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
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

        logger.info(f"DynamoDB service initialized (region={region})")

    async def save_pipeline(self, pipeline_data: Dict[str, Any]) -> bool:
        """Save initial pipeline record when a PR comes in."""
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

    async def update_pipeline_status(
        self,
        pipeline_id: str,
        created_at: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Update pipeline status after agent completes."""
        try:
            # Build update expression
            update_parts = []
            expression_values = {}
            expression_names = {}

            for key, value in updates.items():
                placeholder = f":{key}"
                name_placeholder = f"#{key}"
                update_parts.append(f"{name_placeholder} = {placeholder}")
                expression_values[placeholder] = _convert_floats(value)
                expression_names[name_placeholder] = key

            update_expression = "SET " + ", ".join(update_parts)

            self.pipelines_table.update_item(
                Key={"pipeline_id": pipeline_id, "created_at": created_at},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names,
            )
            logger.info(f"Updated pipeline {pipeline_id}: {list(updates.keys())}")
            return True
        except ClientError as e:
            logger.error(f"Failed to update pipeline: {e}")
            return False

    async def save_agent_decision(
        self,
        pipeline_id: str,
        agent_name: str,
        report: Dict[str, Any],
    ) -> bool:
        """Save the full agent decision report."""
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

    async def get_pipeline(self, pipeline_id: str, created_at: str) -> Optional[Dict[str, Any]]:
        """Retrieve a pipeline record by ID."""
        try:
            response = self.pipelines_table.get_item(
                Key={"pipeline_id": pipeline_id, "created_at": created_at}
            )
            item = response.get("Item")
            return _restore_decimals(item) if item else None
        except ClientError as e:
            logger.error(f"Failed to get pipeline: {e}")
            return None

    async def check_existing_review_for_sha(
        self,
        repo: str,
        head_sha: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if we've already reviewed this exact commit SHA.
        Used to skip re-running expensive AI analysis on the same code.
        """
        try:
            response = self.decisions_table.scan(
                FilterExpression="contains(#report.#repo, :repo) AND #report.#head_sha = :sha AND #report.#agent = :agent",
                ExpressionAttributeNames={
                    "#report": "report",
                    "#repo": "repo",
                    "#head_sha": "head_sha",
                    "#agent": "agent",
                },
                ExpressionAttributeValues={
                    ":repo": repo,
                    ":sha": head_sha,
                    ":agent": "ReviewAgent",
                },
                Limit=1,
            )
            items = response.get("Items", [])
            return _restore_decimals(items[0]) if items else None
        except ClientError as e:
            logger.warning(f"Could not check existing review: {e}")
            return None


# Global singleton
_service: Optional[DynamoDBService] = None


def get_dynamodb_service() -> DynamoDBService:
    global _service
    if _service is None:
        _service = DynamoDBService()
    return _service