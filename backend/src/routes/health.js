import express from 'express';

const router = express.Router();

router.get('/', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'agentops-backend',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

router.get('/deep', async (req, res) => {
  // TODO: Add real health checks for DynamoDB, SQS, Redis as they're integrated
  res.json({
    status: 'healthy',
    service: 'agentops-backend',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks: {
      api: 'healthy',
      dynamodb: 'pending_integration',
      sqs: 'pending_integration',
      redis: 'pending_integration',
    },
  });
});

export default router;
