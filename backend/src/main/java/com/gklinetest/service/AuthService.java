package com.gklinetest.service;

import com.gklinetest.dto.LoginRequest;
import com.gklinetest.dto.LoginResponse;
import com.gklinetest.dto.RegisterRequest;

public interface AuthService {

    LoginResponse login(LoginRequest request);

    void register(RegisterRequest request);
}
