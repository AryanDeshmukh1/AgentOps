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
import { registerIO, CHANNELS } from './services/wsBroadcaster.js';
import eventsRoutes from './routes/events.js';



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
      // Allow no-origin (file://, curl, mobile apps) in development
      if (!origin) return callback(null, true);
      const allowed = [CORS_ORIGIN, 'http://localhost:3000', 'http://localhost:4000', 'null'];
      if (allowed.includes(origin) || origin.startsWith('file://')) {
        return callback(null, true);
      }
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

// Routes
app.use('/api/webhooks', webhookRoutes);
app.use('/api/health', healthRoutes);
app.use('/health', healthRoutes);
app.use('/api/pipelines', pipelineRoutes);
app.use('/api/approvals', approvalRoutes);
app.use('/api/deployments', deploymentRoutes);
app.use('/api/events', eventsRoutes);


// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'AgentOps Backend',
    version: '0.1.0',
    status: 'running',
    timestamp: new Date().toISOString(),
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not Found', path: req.path });
});

// Error handler
app.use((err, req, res, next) => {
  logger.error(err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
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

export { app, io };
