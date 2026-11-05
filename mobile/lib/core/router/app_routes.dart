/// Route paths. Build links with these, never with string literals.
abstract final class AppRoutes {
  static const signIn = '/sign-in';
  static const home = '/home';
  static const detector = '$home/detector';
  static const chat = '$home/chat';
  static const approvals = '/approvals';
  static const activity = '/activity';
  static const audit = '/audit';
  static const account = '/account';

  /// Path parameter for an approval id.
  static const approvalIdParam = 'id';

  static String approvalDetails(String id) => '$approvals/$id';
}
