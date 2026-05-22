package com.exem.inspector.common.web;

/**
 * 모든 REST 응답의 표준 봉투(envelope).
 *
 * <p>화면/엔드포인트는 성공이면 {@code ok(data)}, 실패면 {@code error(message)} 로 응답한다.
 * 기존 Python 의 화면별 _warn_box(err) 분기를 구조로 통일한다(I절 — 백엔드 공통화).
 *
 * @param <T> data 페이로드 타입
 */
public class ApiResponse<T> {

    private final boolean ok;
    private final String error;
    private final T data;

    private ApiResponse(boolean ok, String error, T data) {
        this.ok = ok;
        this.error = error;
        this.data = data;
    }

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(true, null, data);
    }

    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(false, message, null);
    }

    public boolean isOk() {
        return ok;
    }

    public String getError() {
        return error;
    }

    public T getData() {
        return data;
    }
}
