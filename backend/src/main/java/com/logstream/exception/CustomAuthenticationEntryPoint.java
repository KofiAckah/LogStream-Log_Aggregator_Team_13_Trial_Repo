package com.logstream.exception;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.UnsupportedJwtException;
import io.jsonwebtoken.security.SignatureException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.*;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;


@Slf4j
@Component
public class CustomAuthenticationEntryPoint implements AuthenticationEntryPoint {

    /*
     * A dedicated ObjectMapper is used here instead of the shared Spring-managed bean.
     * Filter-chain components execute outside the MVC context and the shared bean may
     * not be available during early startup phases.
     */
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

    @Override
    public void commence(HttpServletRequest request,
                         HttpServletResponse response,
                         AuthenticationException authException) throws IOException {

        // JWT exceptions are often wrapped inside a BadCredentialsException or
        // InsufficientAuthenticationException by the JwtAuthenticationFilter.
        // Unwrap to get the real cause for accurate classification.
        Throwable root = (authException.getCause() != null)
                ? authException.getCause()
                : authException;

        String exceptionName = root.getClass().getSimpleName();
        String message = resolveMessage(authException, root);

        // Use error-level logging for unexpected service failures; warn for normal auth failures.
        if (root instanceof AuthenticationServiceException) {
            log.error("Authentication service error on '{}': {}", request.getRequestURI(), root.getMessage(), root);
        } else {
            log.warn("Authentication failure [{}] on '{}': {}", exceptionName, request.getRequestURI(), root.getMessage());
        }

        writeJsonResponse(response,  HttpServletResponse.SC_UNAUTHORIZED,  message);
    }

    /**
     * Maps each exception type to a safe, user-friendly message.
     * Never exposes stack traces or internal system details.
     */
    private String resolveMessage(AuthenticationException authException, Throwable root) {

        // ── JWT Exceptions (wrapped as cause by JwtAuthenticationFilter) ──────
        if (root instanceof ExpiredJwtException) {
            return "Your session has expired. Please log in again.";
        }
        if (root instanceof MalformedJwtException) {
            return "The provided authentication token is malformed.";
        }
        if (root instanceof SignatureException) {
            return "The authentication token signature is invalid.";
        }
        if (root instanceof UnsupportedJwtException) {
            return "The authentication token format is not supported.";
        }
        if (root instanceof JwtException) {
            return "The authentication token is invalid.";
        }
        if (root instanceof IllegalArgumentException) {
            return "No authentication token was provided in the request.";
        }

        // ── Spring Security Authentication Exceptions ─────────────────────────
        if (authException instanceof BadCredentialsException) {
            return "Invalid username or password.";
        }
        if (authException instanceof UsernameNotFoundException) {
            return "No account found for the provided credentials.";
        }
        if (authException instanceof AccountExpiredException) {
            return "Your account has expired. Please contact support.";
        }

        if (authException instanceof AuthenticationCredentialsNotFoundException) {
            return "No authentication credentials were found in the request.";
        }
        if (authException instanceof InsufficientAuthenticationException) {
            return "Full authentication is required to access this resource.";
        }
        if (authException instanceof AuthenticationServiceException) {
            return "An internal authentication error occurred. Please try again later.";
        }

        return "Authentication failed. Please check your credentials and try again.";
    }

    private void writeJsonResponse(HttpServletResponse response,
                                   int status,
                                   String message) throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("message", message);

        MAPPER.writeValue(response.getOutputStream(), body);
    }
}