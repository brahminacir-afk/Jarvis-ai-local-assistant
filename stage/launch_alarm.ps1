$xml = [Windows.Data.Xml.Dom.XmlDocument]::new();
$xml.LoadXml([string]'<toast scenario="alarm"><visual><binding template="ToastGeneric"><text>⏰ Assistant IA Desktop</text><text>C''est l''heure de votre alarme !</text></binding></visual><audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true"/><actions><action content="Snooze" arguments="snooze" activationType="system"/><action content="Dismiss" arguments="dismiss" activationType="system"/></actions></toast>');
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Windows.SystemToast.Background").Show($toast);
