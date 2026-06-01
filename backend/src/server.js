import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import dotenv from 'dotenv';
import webhookRoutes from './routes/webhooks.js';
import pipelineRoutes from './routes/pipelines.js';
import healthRoutes from './routes/health.js';
import logger from './utils/logger.js';
import approvalRoutes from './routes/approvals.js';
import deploymentRoutes from './routes/deployments.js';
import incidentRoutes from './routes/incidents.js';
import { registerIO, CHANNELS } from './services/wsBroadcaster.js';
import eventsRoutes from './routes/events.js';
import swaggerUi from "swagger-ui-express";
import YAML from "yaml";
import fs from "fs";
import { fileURLToPath } from "url";
import path from "path";
import { requestIdMiddleware, errorHandler, notFoundHandler } from "./middleware/errorHandler.js";
import { publicLimiter, readLimiter } from "./middleware/rateLimit.js";



dotenv.config();

const PORT = process.env.BACKEND_PORT || 4000;
const HOST = process.env.BACKEND_HOST || '0.0.0.0';
const CORS_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:3000';

const app = express();
const httpServer = createServer(app);

// Socket.io for real-time dashboard updates
const io = new SocketServer(httpServer, {
  cors: {
    origin: (origin, callback) => {
      if (!origin) return callback(null, true);
      const isAllowed =
        origin === CORS_ORIGIN ||
        origin.startsWith('http://localhost') ||
        origin.startsWith('file://') ||
        origin.endsWith('.vercel.app') ||
        origin.endsWith('.railway.app') ||
        origin.endsWith('.up.railway.app');
      if (isAllowed) return callback(null, true);
      callback(new Error('CORS rejected for origin: ' + origin));
    },
    methods: ['GET', 'POST'],
    credentials: true,
  },
});

// Middleware
app.use(helmet());
app.use(cors({ origin: CORS_ORIGIN, credentials: true }));
// Capture raw body for webhook signature verification
app.use(express.json({
  limit: '10mb',
  verify: (req, res, buf) => {
    req.rawBody = buf;
  },
}));
app.use(express.urlencoded({ extended: true }));
app.use(morgan('dev'));

// Attach request_id to every request
app.use(requestIdMiddleware);

// Mount OpenAPI / Swagger UI at /api/docs
try {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const specPath = path.join(__dirname, ".", "openapi.yaml");
  if (fs.existsSync(specPath)) {
    const spec = YAML.parse(fs.readFileSync(specPath, "utf-8"));
    app.use("/api/docs", swaggerUi.serve, swaggerUi.setup(spec));
    logger.info("[OpenAPI] Swagger UI mounted at /api/docs");
  } else {
    logger.warn("[OpenAPI] openapi.yaml not found, skipping Swagger UI");
  }
} catch (err) {
  logger.error(`[OpenAPI] Failed to load spec: ${err.message}`);
}

// Routes — public endpoints get stricter rate limits
app.use('/api/webhooks', publicLimiter, webhookRoutes);
app.use('/api/health', healthRoutes);
app.use('/health', healthRoutes);
app.use('/api/pipelines', readLimiter, pipelineRoutes);
app.use('/api/approvals', readLimiter, approvalRoutes);
app.use('/api/deployments', readLimiter, deploymentRoutes);
app.use('/api/events', publicLimiter, eventsRoutes);
app.use('/api/incidents', readLimiter, incidentRoutes);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'AgentOps Backend',
    version: '0.1.0',
    status: 'running',
    timestamp: new Date().toISOString(),
  });
});


// WebSocket connections
// WebSocket: auth handshake
const WS_SHARED_TOKEN = process.env.WS_SHARED_TOKEN;
const VALID_CHANNELS = new Set(Object.values(CHANNELS));

io.use((socket, next) => {
  const token = socket.handshake.auth?.token || socket.handshake.query?.token;
  if (!WS_SHARED_TOKEN) {
    logger.warn('[WS] WS_SHARED_TOKEN not configured — allowing all connections (dev only)');
    return next();
  }
  if (token !== WS_SHARED_TOKEN) {
    logger.warn(`[WS] Auth rejected for ${socket.id}: bad token`);
    return next(new Error('Authentication required'));
  }
  next();
});

io.on('connection', (socket) => {
  logger.info(`[WS] Client connected: ${socket.id}`);

  // Subscribe to one or more channels
  socket.on('subscribe', (channels) => {
    const list = Array.isArray(channels) ? channels : [channels];
    const joined = [];
    const rejected = [];
    for (const ch of list) {
      if (VALID_CHANNELS.has(ch)) {
        socket.join(ch);
        joined.push(ch);
      } else {
        rejected.push(ch);
      }
    }
    socket.emit('subscribed', { joined, rejected });
    logger.info(`[WS] ${socket.id} subscribed to: ${joined.join(', ')}`);
  });

  socket.on('unsubscribe', (channels) => {
    const list = Array.isArray(channels) ? channels : [channels];
    for (const ch of list) socket.leave(ch);
    socket.emit('unsubscribed', { channels: list });
  });

  socket.on('disconnect', () => {
    logger.info(`[WS] Client disconnected: ${socket.id}`);
  });
});

registerIO(io);

// Start server
httpServer.listen(PORT, HOST, () => {
  logger.info(`AgentOps Backend running on http://${HOST}:${PORT}`);
  logger.info(`WebSocket server ready`);
  logger.info(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  httpServer.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
});

// 404 + error handlers 
app.use(notFoundHandler);
app.use(errorHandler);

export { app, io };
