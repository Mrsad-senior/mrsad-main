import 'package:flutter/widgets.dart';
import 'package:mirsad/app.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/di/injection.dart';
import 'package:mirsad/core/router/app_router.dart';
import 'package:mirsad/core/widgets/config_error_app.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final config = AppConfig.fromEnvironment();
  final problem = config.validate();
  if (problem != null) {
    runApp(ConfigErrorApp(problem: problem));
    return;
  }

  await configureDependencies(config);
  // Read the session before building the router, so the first screen is
  // already the right one.
  final authCubit = getIt<AuthCubit>()..start();
  runApp(
    MirsadApp(
      router: createAppRouter(
        authCubit: authCubit,
        showMockSignInHint: config.useMock,
      ),
      localeCubit: getIt(),
      authCubit: authCubit,
      clock: getIt(),
    ),
  );
}
