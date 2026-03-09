package com.logstream.service;

import com.logstream.dto.LogEntryResponse;
import com.logstream.dto.LogSearchRequest;
import com.logstream.model.LogEntry;
import com.logstream.repository.LogEntryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class SearchService {

    private final LogEntryRepository logEntryRepository;

    public List<LogEntryResponse> searchLogs(LogSearchRequest request) {
        PageRequest pageable = PageRequest.of(request.getPage(), request.getSize());

        Specification<LogEntry> spec = Specification.where(null);

        if (request.getServiceName() != null && !request.getServiceName().isBlank()) {
            spec = spec.and((root, query, cb) ->
                cb.equal(root.get("serviceName"), request.getServiceName()));
        }

        if (request.getLevel() != null) {
            spec = spec.and((root, query, cb) ->
                cb.equal(root.get("level"), request.getLevel()));
        }

        if (request.getStartTime() != null && !request.getStartTime().isBlank()) {
            Instant start = Instant.parse(request.getStartTime());
            spec = spec.and((root, query, cb) ->
                cb.greaterThanOrEqualTo(root.get("timestamp"), start));
        }

        if (request.getEndTime() != null && !request.getEndTime().isBlank()) {
            Instant end = Instant.parse(request.getEndTime());
            spec = spec.and((root, query, cb) ->
                cb.lessThanOrEqualTo(root.get("timestamp"), end));
        }

        if (request.getKeyword() != null && !request.getKeyword().isBlank()) {
            String like = "%" + request.getKeyword().toLowerCase() + "%";
            spec = spec.and((root, query, cb) ->
                cb.like(cb.lower(root.get("message")), like));
        }

        Page<LogEntry> results = logEntryRepository.findAll(spec, pageable);
        return results.map(this::mapToResponse).getContent();
    }

    public LogEntryResponse getLogById(UUID id) {
        LogEntry entry = logEntryRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Log entry not found: " + id));
        return mapToResponse(entry);
    }

    private LogEntryResponse mapToResponse(LogEntry e) {
        return LogEntryResponse.builder()
            .id(e.getId()).serviceName(e.getServiceName()).timestamp(e.getTimestamp())
            .level(e.getLevel()).message(e.getMessage()).metadata(e.getMetadata())
            .source(e.getSource()).traceId(e.getTraceId()).createdAt(e.getCreatedAt())
            .build();
    }
}
