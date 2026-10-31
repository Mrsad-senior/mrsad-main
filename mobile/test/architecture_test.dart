import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Guards the Clean Architecture rules in CLAUDE.md.
void main() {
  final featureFiles = _dartFilesUnder('lib/features');

  test('domain layers import only pure Dart', () {
    const allowedPrefixes = [
      'dart:',
      'package:equatable/',
      'package:fpdart/',
      'package:meta/',
      'package:mirsad/core/errors/failure.dart',
      'package:mirsad/core/utils/',
    ];
    final violations = <String>[];
    for (final file in featureFiles.where((f) => f.layer == 'domain')) {
      for (final import in file.imports) {
        final ownDomain = 'package:mirsad/features/${file.feature}/domain/';
        final allowed =
            import.startsWith(ownDomain) ||
            allowedPrefixes.any(import.startsWith);
        if (!allowed) violations.add('${file.path} imports $import');
      }
    }
    expect(violations, isEmpty);
  });

  test('features do not import other features', () {
    final violations = <String>[];
    for (final file in featureFiles) {
      for (final import in file.imports) {
        final match = RegExp(
          r'^package:mirsad/features/(\w+)/',
        ).firstMatch(import);
        if (match != null && match.group(1) != file.feature) {
          violations.add('${file.path} imports $import');
        }
      }
    }
    expect(violations, isEmpty);
  });
}

class _SourceFile {
  _SourceFile(this.path, this.feature, this.layer, this.imports);

  final String path;
  final String feature;
  final String layer;
  final List<String> imports;
}

List<_SourceFile> _dartFilesUnder(String root) {
  final directory = Directory(root);
  if (!directory.existsSync()) return const [];
  final importPattern = RegExp(r'''^import\s+['"]([^'"]+)['"]''');
  return directory
      .listSync(recursive: true)
      .whereType<File>()
      .where((file) => file.path.endsWith('.dart'))
      .map((file) {
        final path = file.path.replaceAll(r'\', '/');
        final segments = path.split('/');
        final featuresIndex = segments.indexOf('features');
        final imports = file
            .readAsLinesSync()
            .map((line) => importPattern.firstMatch(line)?.group(1))
            .whereType<String>()
            .toList();
        return _SourceFile(
          path,
          segments[featuresIndex + 1],
          segments[featuresIndex + 2],
          imports,
        );
      })
      .toList();
}
