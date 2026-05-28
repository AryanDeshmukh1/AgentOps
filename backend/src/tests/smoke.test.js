import { mockClient } from "aws-sdk-client-mock";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, PutCommand, GetCommand } from "@aws-sdk/lib-dynamodb";

describe("Smoke: Jest harness", () => {
  test("Jest runs", () => {
    expect(1 + 1).toBe(2);
  });

  test("Async tests work", async () => {
    const result = await Promise.resolve(42);
    expect(result).toBe(42);
  });
});

describe("Smoke: aws-sdk-client-mock", () => {
  const dynamoMock = mockClient(DynamoDBDocumentClient);

  beforeEach(() => {
    dynamoMock.reset();
  });

  test("PutCommand is mocked", async () => {
    dynamoMock.on(PutCommand).resolves({});
    const baseClient = new DynamoDBClient({ region: "ca-central-1" });
    const client = DynamoDBDocumentClient.from(baseClient);
    const result = await client.send(new PutCommand({
      TableName: "AgentOps-Pipelines",
      Item: { pipeline_id: "test_001", created_at: "2026-05-28" },
    }));
    expect(result).toEqual({});
    expect(dynamoMock.calls()).toHaveLength(1);
  });

  test("GetCommand returns mocked data", async () => {
    dynamoMock.on(GetCommand).resolves({
      Item: { pipeline_id: "test_001", status: "complete" },
    });
    const baseClient = new DynamoDBClient({ region: "ca-central-1" });
    const client = DynamoDBDocumentClient.from(baseClient);
    const result = await client.send(new GetCommand({
      TableName: "AgentOps-Pipelines",
      Key: { pipeline_id: "test_001", created_at: "2026-05-28" },
    }));
    expect(result.Item.status).toBe("complete");
  });
});