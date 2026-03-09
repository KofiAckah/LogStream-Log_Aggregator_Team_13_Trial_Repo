package com.logstream.model;

import java.io.Serializable;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public class LogEntryId implements Serializable {

    private Instant timestamp;
    private UUID id;

    public LogEntryId() {
    }

    public LogEntryId(Instant timestamp, UUID id) {
        this.timestamp = timestamp;
        this.id = id;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof LogEntryId that)) return false;
        return Objects.equals(timestamp, that.timestamp) && Objects.equals(id, that.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(timestamp, id);
    }
}