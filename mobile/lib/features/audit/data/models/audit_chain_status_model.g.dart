// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'audit_chain_status_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

AuditChainStatusModel _$AuditChainStatusModelFromJson(
  Map<String, dynamic> json,
) => AuditChainStatusModel(
  valid: json['valid'] as bool,
  brokenAt: (json['broken_at'] as num?)?.toInt(),
);

Map<String, dynamic> _$AuditChainStatusModelToJson(
  AuditChainStatusModel instance,
) => <String, dynamic>{'valid': instance.valid, 'broken_at': instance.brokenAt};
