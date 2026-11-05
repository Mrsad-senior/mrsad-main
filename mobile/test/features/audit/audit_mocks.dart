import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/domain/repositories/audit_repository.dart';
import 'package:mirsad/features/audit/domain/usecases/verify_audit_chain.dart';
import 'package:mocktail/mocktail.dart';

class MockAuditRepository extends Mock implements AuditRepository {}

class MockAuditDataSource extends Mock implements AuditDataSource {}

class MockVerifyAuditChain extends Mock implements VerifyAuditChain {}
