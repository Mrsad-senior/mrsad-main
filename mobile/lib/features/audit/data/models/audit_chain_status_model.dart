import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

part 'audit_chain_status_model.g.dart';

/// The audit fields of `GET /api/stats/overview`. Only the fields the app
/// uses are read.
@JsonSerializable(createToJson: false)
class AuditChainStatusModel {
  const AuditChainStatusModel({required this.auditOk, this.auditFirstBadSeq});

  factory AuditChainStatusModel.fromJson(Map<String, dynamic> json) =>
      _$AuditChainStatusModelFromJson(json);

  /// The result of a full chain verification, which the gateway reuses for
  /// up to 30 seconds. Null when the gateway could not run it.
  final bool? auditOk;

  /// The first entry that fails verification. Proposed in
  /// docs/API_CONTRACT.md: the gateway does not send it yet.
  final int? auditFirstBadSeq;

  /// A valid chain has no broken entry, whatever the gateway sent. The API
  /// source rejects a null [auditOk] before this is called.
  AuditChainStatus toEntity() {
    final valid = auditOk ?? false;
    return AuditChainStatus(
      valid: valid,
      brokenAt: valid ? null : auditFirstBadSeq,
    );
  }
}
