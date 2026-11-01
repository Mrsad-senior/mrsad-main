// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'call_decision_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

CallDecisionModel _$CallDecisionModelFromJson(Map<String, dynamic> json) =>
    CallDecisionModel(
      riskScore: (json['risk_score'] as num).toDouble(),
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => ApprovalReasonModel.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
