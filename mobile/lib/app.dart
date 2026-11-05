import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/locale_cubit.dart';
import 'package:mirsad/core/theme/app_theme.dart';
import 'package:mirsad/core/utils/clock.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// The root widget: themes, languages, the session and the router.
class MirsadApp extends StatelessWidget {
  const MirsadApp({
    required this.router,
    required this.localeCubit,
    required this.authCubit,
    required this.clock,
    super.key,
  });

  final GoRouter router;
  final LocaleCubit localeCubit;
  final AuthCubit authCubit;
  final Clock clock;

  @override
  Widget build(BuildContext context) {
    return RepositoryProvider<Clock>.value(
      value: clock,
      child: MultiBlocProvider(
        providers: [
          BlocProvider<LocaleCubit>.value(value: localeCubit),
          BlocProvider<AuthCubit>.value(value: authCubit),
        ],
        child: BlocBuilder<LocaleCubit, Locale?>(
          builder: (context, locale) => MaterialApp.router(
            onGenerateTitle: (context) => context.l10n.appTitle,
            debugShowCheckedModeBanner: false,
            theme: AppTheme.light(),
            darkTheme: AppTheme.dark(),
            locale: locale,
            supportedLocales: AppLocalizations.supportedLocales,
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            routerConfig: router,
          ),
        ),
      ),
    );
  }
}
