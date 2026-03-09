package com.logstream.exception;

/**
 * Exception thrown when user doesn't have required role
 */
public class AuthorizationException extends RuntimeException {
    public AuthorizationException(String message) {
        super(message);
    }
}
