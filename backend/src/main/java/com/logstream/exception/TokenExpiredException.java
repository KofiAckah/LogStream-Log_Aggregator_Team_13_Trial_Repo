package com.logstream.exception;

/**
 * Exception thrown when token has expired
 */
public class TokenExpiredException extends RuntimeException {
    public TokenExpiredException(String message) {
        super(message);
    }
}
