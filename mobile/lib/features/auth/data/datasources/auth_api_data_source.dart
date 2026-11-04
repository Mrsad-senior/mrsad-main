import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/data/models/login_request_model.dart';
import 'package:mirsad/features/auth/data/models/login_response_model.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';

/// Sign-in with a gateway account (`POST /api/auth/login`). The gateway signs
/// its own tokens.
///
/// The session lives in memory only, so closing the app signs the reviewer
/// out, as in the web approver app. The gateway has no sign-out endpoint;
/// its tokens expire after 12 hours by default.
class AuthApiDataSource implements AuthDataSource {
  AuthApiDataSource(this._dio);

  static const path = '/api/auth/login';

  final Dio _dio;
  final StreamController<ReviewerModel?> _changes =
      StreamController.broadcast();

  ReviewerModel? _reviewer;
  String? _token;

  @override
  ReviewerModel? get currentReviewer => _reviewer;

  @override
  Stream<ReviewerModel?> watchReviewer() async* {
    yield _reviewer;
    yield* _changes.stream;
  }

  @override
  Future<ReviewerModel> signIn({
    required String email,
    required String password,
  }) async {
    final request = LoginRequestModel(
      username: email.trim(),
      password: password,
    );
    final LoginResponseModel login;
    try {
      login = await callGateway(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          path,
          data: request.toJson(),
        );
        return LoginResponseModel.fromJson(
          response.data ??
              (throw const DataFormatException('Empty login response')),
        );
      });
    } on UnauthorizedException catch (error) {
      // On this endpoint a 401 means a wrong username or password.
      throw InvalidCredentialsException(error.message);
    }
    final reviewer = login.toReviewer();
    _token = login.accessToken;
    _set(reviewer);
    return reviewer;
  }

  @override
  Future<void> signOut() async {
    _token = null;
    _set(null);
  }

  @override
  Future<String?> accessToken() async => _token;

  Future<void> dispose() => _changes.close();

  void _set(ReviewerModel? reviewer) {
    _reviewer = reviewer;
    _changes.add(reviewer);
  }
}
