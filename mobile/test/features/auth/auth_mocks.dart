import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';
import 'package:mirsad/features/auth/domain/usecases/get_current_reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_in.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_out.dart';
import 'package:mirsad/features/auth/domain/usecases/watch_reviewer.dart';
import 'package:mocktail/mocktail.dart';

class MockAuthRepository extends Mock implements AuthRepository {}

class MockAuthDataSource extends Mock implements AuthDataSource {}

class MockSignIn extends Mock implements SignIn {}

class MockSignOut extends Mock implements SignOut {}

class MockWatchReviewer extends Mock implements WatchReviewer {}

class MockGetCurrentReviewer extends Mock implements GetCurrentReviewer {}

const reviewer = Reviewer(id: 'rev_1', email: 'reviewer@bank.example');
