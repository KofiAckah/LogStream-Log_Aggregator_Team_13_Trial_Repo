package com.logstream.common.response;

import lombok.Builder;
import lombok.Getter;

import java.util.Map;

@Getter
@Builder
public class ErrorResponse {
    private final String message;
    private final Map<String, String> errors;
}

