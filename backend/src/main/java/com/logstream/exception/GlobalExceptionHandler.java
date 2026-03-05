package com.logstream.exception;

import com.logstream.common.response.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.*;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;


@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // ══════════════════════════════════════════════════════════════════════════
    // 400 – Bad Request
    // ══════════════════════════════════════════════════════════════════════════

    /**
     * Bean validation failures on @RequestBody fields.
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleMethodArgumentNotValid(
            MethodArgumentNotValidException ex) {

        Map<String, String> errors = Stream.concat(
                ex.getBindingResult().getFieldErrors().stream()
                        .map(e -> Map.entry(e.getField(), e.getDefaultMessage())),
                ex.getBindingResult().getGlobalErrors().stream()
                        .map(e -> Map.entry(e.getObjectName(), e.getDefaultMessage()))
        ).collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue,
                (existing, replacement) -> existing));

        log.warn("Validation failure: {}", errors);
        return ResponseEntity.badRequest()
                .body(ErrorResponse.builder().errors(errors).build());
    }

    /**
     * Bean validation failures on @RequestParam / @PathVariable.
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ErrorResponse> handleConstraintViolation(
            ConstraintViolationException ex) {

        Map<String, String> errors = ex.getConstraintViolations().stream()
                .collect(Collectors.toMap(
                        cv -> cv.getPropertyPath().toString(),
                        ConstraintViolation::getMessage,
                        (existing, replacement) -> existing
                ));

        log.warn("Constraint violation: {}", errors);
        return ResponseEntity.badRequest()
                .body(ErrorResponse.builder().errors(errors).build());
    }

    @ExceptionHandler(BadRequestException.class)
    public ResponseEntity<ErrorResponse> handleBadRequest(BadRequestException ex) {
        log.warn("Bad request: {}", ex.getMessage());
        return ResponseEntity.badRequest()
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }

    @ExceptionHandler(InvalidDataException.class)
    public ResponseEntity<ErrorResponse> handleInvalidData(InvalidDataException ex) {
        log.warn("Invalid data: {}", ex.getMessage());
        return ResponseEntity.badRequest()
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }



    @ExceptionHandler({
            BadCredentialsException.class,
            UsernameNotFoundException.class
    })
    public ResponseEntity<ErrorResponse> handleBadCredentials(AuthenticationException ex) {
        // Generic message intentional — do not reveal whether the user exists.
        log.warn("Authentication failure in MVC layer [{}]: {}", ex.getClass().getSimpleName(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ErrorResponse.builder()
                        .message("Invalid username or password.")
                        .build());
    }

    @ExceptionHandler({
            AccountExpiredException.class,
            LockedException.class,
            DisabledException.class,
            CredentialsExpiredException.class
    })
    public ResponseEntity<ErrorResponse> handleAccountStatus(AuthenticationException ex) {
        log.warn("Account status failure in MVC layer [{}]: {}", ex.getClass().getSimpleName(), ex.getMessage());
        String message = resolveAccountStatusMessage(ex);
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ErrorResponse.builder().message(message).build());
    }

    /**
     * Custom domain token exceptions (thrown from token validation services,
     * not from the Security filter chain).
     */
    @ExceptionHandler({
            TokenNotFoundException.class,
            TokenExpiredException.class,
            InvalidTokenException.class
    })
    public ResponseEntity<ErrorResponse> handleTokenExceptions(RuntimeException ex) {
        log.warn("Token error [{}]: {}", ex.getClass().getSimpleName(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 403 – Forbidden
    // ══════════════════════════════════════════════════════════════════════════

    /*
     * NOTE: AccessDeniedException from the Security filter chain is handled by
     * CustomAccessDeniedHandler. This handler covers AccessDeniedException thrown
     * from @Service code or @PreAuthorize annotations evaluated inside the MVC layer.
     */

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ErrorResponse> handleAccessDenied(AccessDeniedException ex,
                                                            HttpServletRequest request) {
        log.warn("Access denied in MVC layer on '{}': {}", request.getRequestURI(), ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(ErrorResponse.builder()
                        .message("You do not have permission to access this resource.")
                        .build());
    }

    /**
     * Custom domain authorization exception (thrown when role checks fail in service layer).
     */
    @ExceptionHandler(AuthorizationException.class)
    public ResponseEntity<ErrorResponse> handleAuthorizationException(AuthorizationException ex) {
        log.warn("Authorization failure: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 404 – Not Found
    // ══════════════════════════════════════════════════════════════════════════

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleResourceNotFound(ResourceNotFoundException ex) {
        log.warn("Resource not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }

    /**
     * Handles missing static resources (e.g. /favicon.ico) — avoids 500 noise in logs.
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ErrorResponse> handleNoStaticResource(NoResourceFoundException ex) {
        log.debug("Static resource not found: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ErrorResponse.builder()
                        .message("Resource not found: " + ex.getMessage())
                        .build());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 409 – Conflict
    // ══════════════════════════════════════════════════════════════════════════

    @ExceptionHandler(DuplicateResourceException.class)
    public ResponseEntity<ErrorResponse> handleDuplicateResource(DuplicateResourceException ex) {
        log.warn("Duplicate resource: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(ErrorResponse.builder().message(ex.getMessage()).build());
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ErrorResponse> handleDataIntegrityViolation(
            DataIntegrityViolationException ex) {
        String cause = ex.getMostSpecificCause() != null
                ? ex.getMostSpecificCause().getMessage()
                : ex.getMessage();
        log.warn("Data integrity violation: {}", cause);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(ErrorResponse.builder()
                        .message("A data conflict occurred. The resource may already exist.")
                        .build());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 500 – Internal Server Error (catch-all, must be last)
    // ══════════════════════════════════════════════════════════════════════════

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex, HttpServletRequest request) {
        // Log full stack trace for unexpected errors — critical for debugging production issues.
        log.error("Unexpected error on '{}': {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ErrorResponse.builder()
                        .message("An unexpected error occurred. Please contact support if this persists.")
                        .build());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // Private helpers
    // ══════════════════════════════════════════════════════════════════════════

    private String resolveAccountStatusMessage(AuthenticationException ex) {
        if (ex instanceof LockedException)            return "Your account is locked. Please contact support.";
        if (ex instanceof DisabledException)          return "Your account has been disabled. Please contact support.";
        if (ex instanceof AccountExpiredException)    return "Your account has expired. Please contact support.";
        if (ex instanceof CredentialsExpiredException) return "Your password has expired. Please reset your password.";
        return "Your account is not in a valid state. Please contact support.";
    }
}