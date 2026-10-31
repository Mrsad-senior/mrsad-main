import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

part 'audit_chain_status_model.g.dart';

/// Body of `GET /audit/verify`.
@JsonSerializable()
class AuditChainStatusModel {
  const AuditChainStatusModel({required this.valid, this.brokenAt});

  factory AuditChainStatusModel.fromJson(Map<String, dynamic> json) =>
      _$AuditChainStatusModelFromJson(json);

  final bool valid;
  final int? brokenAt;

  Map<String, dynamic> toJson() => _$AuditChainStatusModelToJson(this);

  /// A valid chain has no broken entry, whatever the gateway sent.
  AuditChainStatus toEntity() =>
      AuditChainStatus(valid: valid, brokenAt: valid ? null : brokenAt);
}
