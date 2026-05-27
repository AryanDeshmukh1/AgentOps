/**
 * WebSocket Broadcaster — emits events to channel rooms.
 *
 * Channels (Socket.IO rooms):
 *   - "pipelines"   — pipeline state changes (created, agent stage transitions, complete)
 *   - "approvals"   — approval state transitions
 *   - "deployments" — deployment lifecycle (provisioning, traffic shifts, promote, rollback)
 *   - "incidents"   — anomalies fired, root cause attached, status changes
 *
 * Event envelope (all events have this shape):
 *   {
 *     channel: "deployments",
 *     type: "deployment.traffic_shifted",
 *     payload: { ... },
 *     ts: "2026-05-27T...",
 *     source: "DeployAgent"
 *   }
 */
import logger from "../utils/logger.js";

export const CHANNELS = {
  PIPELINES: "pipelines",
  APPROVALS: "approvals",
  DEPLOYMENTS: "deployments",
  INCIDENTS: "incidents",
};

const VALID_CHANNELS = new Set(Object.values(CHANNELS));

let _io = null;

/** Called once from server.js after Socket.IO server is created. */
export function registerIO(io) {
  _io = io;
  logger.info("[WSBroadcaster] Registered Socket.IO instance");
}

/** Broadcast an event to everyone subscribed to a channel. */
export function broadcast({ channel, type, payload = {}, source = "backend" }) {
  if (!_io) {
    logger.warn("[WSBroadcaster] broadcast() called before registerIO()");
    return false;
  }
  if (!VALID_CHANNELS.has(channel)) {
    logger.warn(`[WSBroadcaster] Unknown channel: ${channel}`);
    return false;
  }
  if (!type) {
    logger.warn("[WSBroadcaster] broadcast() requires a 'type' field");
    return false;
  }

  const envelope = {
    channel,
    type,
    payload,
    ts: new Date().toISOString(),
    source,
  };

  _io.to(channel).emit("event", envelope);
  logger.info(`[WSBroadcaster] ${channel}.${type} → ${_io.sockets.adapter.rooms.get(channel)?.size ?? 0} subscribers`);
  return true;
}

/** Total connected clients (across all channels). For metrics + health endpoints. */
export function connectedClientCount() {
  if (!_io) return 0;
  return _io.sockets.sockets.size;
}

/** Subscribers per channel. Useful for the dashboard's debug page later. */
export function channelStats() {
  if (!_io) return {};
  const stats = {};
  for (const channel of VALID_CHANNELS) {
    stats[channel] = _io.sockets.adapter.rooms.get(channel)?.size ?? 0;
  }
  return stats;
}