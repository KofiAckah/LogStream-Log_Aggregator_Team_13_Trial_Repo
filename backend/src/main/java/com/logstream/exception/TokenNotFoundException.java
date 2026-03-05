package com.logstream.exception;

/**
 * Exception thrown when token is not found
 */
public class TokenNotFoundException extends RuntimeException {
    public TokenNotFoundException(String message) {
        super(message);
    }
}
