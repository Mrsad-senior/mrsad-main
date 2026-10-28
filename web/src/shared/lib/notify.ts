/** System notifications (Notification API), shared by the dashboard and the approver PWA. */

export type NotifyPermission = NotificationPermission | 'unsupported';

export function notificationPermission(): NotifyPermission {
  return typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'unsupported';
}

export async function requestNotificationPermission(): Promise<NotifyPermission> {
  if (notificationPermission() === 'unsupported') return 'unsupported';
  try {
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

export interface SystemNotification {
  title: string;
  body: string;
  /** Same tag replaces an older notification instead of stacking. */
  tag: string;
  /** Opened when the notification is clicked. */
  url: string;
}

/**
 * Prefer the service worker (works on Android, survives the tab being hidden);
 * fall back to the page-level constructor on desktop browsers.
 */
export async function showSystemNotification(n: SystemNotification): Promise<boolean> {
  if (notificationPermission() !== 'granted') return false;
  const options: NotificationOptions = {
    body: n.body,
    tag: n.tag,
    icon: '/assets/icons/icon-192.png',
    badge: '/assets/icons/badge-96.png',
    data: { url: n.url },
  };
  try {
    const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined;
    if (registration) {
      await registration.showNotification(n.title, options);
      return true;
    }
    const notification = new Notification(n.title, options);
    notification.onclick = () => {
      window.focus();
      window.location.assign(n.url);
      notification.close();
    };
    return true;
  } catch {
    return false;
  }
}
