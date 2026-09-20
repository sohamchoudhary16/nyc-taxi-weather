# ADR 0004: IoT Core over a bare Kafka topic for the downlink

**Status:** accepted

## Context

The brief requires the architecture to "send data back to individual cars."
This is a command-and-control channel, not a data pipeline. Two broad
approaches exist:

1. **Managed IoT platform** (AWS IoT Core, Azure IoT Hub), purpose-built for
   device-to-cloud and cloud-to-device communication with identity management,
   device shadow/twin, and offline message queuing.
2. **Bare message broker** (Kafka, RabbitMQ), where the vehicle subscribes to a
   topic partitioned by vehicle ID and polls for commands.

## Decision

Use a **managed IoT platform** (IoT Core or IoT Hub) as the single
bidirectional gateway between vehicles and the cloud.

## Rationale

### What the IoT platform gives us that Kafka does not

| Capability | IoT Core / IoT Hub | Bare Kafka |
|---|---|---|
| Device identity + X.509 cert management | Built-in, per-device provisioning | Manual: you build a PKI layer |
| Device shadow / digital twin | Built-in: cloud writes desired state, device reports actual state | Not a concept: you build a state reconciliation protocol |
| Offline command delivery | Shadow holds desired state; device reads on reconnect | Consumer offset does not distinguish "not yet connected" from "connected and caught up" |
| Command TTL and expiry | Shadow versioning + application-level TTL | Manual: you build TTL logic in the consumer |
| Per-device access control | Policy per device or device group | ACLs per topic, not per consumer identity |
| Protocol support | MQTT (native for constrained devices), HTTPS, WebSocket | Kafka protocol only: heavier client, not designed for embedded/mobile |

### The core argument: offline resilience

A taxi in a tunnel, a parking garage, or a rural area may be offline for
minutes to hours. When it reconnects:

- With **device shadow:** the vehicle reads the latest desired state (which
  may be several commands merged into one), applies non-expired commands, and
  reports its new state. No message replay, no ordering bugs.
- With **Kafka:** the vehicle resumes from its last committed offset and
  replays every command in order, including expired ones it must discard.
  If the consumer was offline for a long time, the offset may have been
  garbage-collected, requiring a full topic replay or a fallback path.

For 11,000 vehicles with intermittent connectivity, the shadow model is
fundamentally simpler and more robust.

### Cost note

IoT Core/Hub pricing is per-message, which at 190M telemetry events/day
could be expensive. The mitigation: telemetry (high volume, lossy) is batched
into 30-second micro-batches at the edge before transmission, reducing message
count by ~6×. Trip events (low volume, must-not-lose) are sent individually.
Commands (very low volume) are negligible.

## Consequences

- The IoT platform becomes a single point of entry for all vehicle
  communication. This simplifies networking (one endpoint, one auth model)
  but creates a platform dependency.
- Downstream systems (Kafka/Kinesis, stream processors) receive events via
  IoT rules/routing, not directly from vehicles. This adds a hop but
  decouples processing from device protocol concerns.
- The team needs IoT platform expertise, which is a less common skill set
  than Kafka administration. Training cost is real.

## Alternatives considered

- **MQTT broker (Mosquitto/EMQX) + Kafka:** avoids the managed-service lock-in
  but requires building identity management, shadow state, and offline
  delivery from scratch. Justified only if the IoT platform's per-message
  cost is prohibitive at scale.
- **HTTP polling:** the vehicle polls a REST API for commands. Simpler but
  wastes bandwidth, increases latency, and does not support push
  notifications. Not viable for sub-minute command delivery.
