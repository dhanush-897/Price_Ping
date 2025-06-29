importScripts('https://www.gstatic.com/firebasejs/9.6.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.6.1/firebase-messaging-compat.js');

firebase.initializeApp({
  // Fill in your Firebase config here
  apiKey: "AIzaSyB-wV6E0rVhkYNDZosgj0lebsjqcog9mXI",
  authDomain: "price-ping-app.firebaseapp.com",
  projectId: "price-ping-app",
  storageBucket: "price-ping-app.appspot.com",
  messagingSenderId: "962158299615",
  appId: "1:1234567890:web:abcdef123456",
  measurementId: "G-123456ABC"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(function(payload) {
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/icon-192x192.png' // Optional: add your app icon here
  };
  self.registration.showNotification(notificationTitle, notificationOptions);
});
