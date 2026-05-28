// Test environment globals. Loaded before every test file.
process.env.AWS_REGION = "ca-central-1";
process.env.AWS_ACCESS_KEY_ID = "testing";
process.env.AWS_SECRET_ACCESS_KEY = "testing";
process.env.NODE_ENV = "test";
process.env.WS_SHARED_TOKEN = "test_token";
process.env.CORS_ORIGIN = "http://localhost:3000";