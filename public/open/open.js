/*
 * Открывает приложение по ссылке, которую передал бот.
 *
 * Бот кладёт в параметр redirect_to адрес приложения — happ://add/…,
 * v2raytun://import/…, sing-box://import-remote-profile?url=… Такой адрес
 * нельзя положить в кнопку Telegram, поэтому он приезжает сюда.
 *
 * Открываем только приложения. Обычный сайт (http и https) по этой ссылке
 * не откроется намеренно: иначе наш адрес стал бы удобной ширмой, за
 * которой любой мог бы увести человека куда угодно, прикрывшись доменом
 * VPaNfi. То же и про javascript: — им подменяют саму эту страницу.
 */
(function () {
  var FORBIDDEN_SCHEMES = [
    "http:",
    "https:",
    "javascript:",
    "data:",
    "blob:",
    "file:",
    "about:",
    "vbscript:",
  ];

  var title = document.getElementById("title");
  var hint = document.getElementById("hint");
  var button = document.getElementById("open");

  function refuse(message) {
    title.textContent = "Ссылка не открылась";
    hint.textContent = message;
    button.hidden = true;
  }

  var target = new URLSearchParams(window.location.search).get("redirect_to");

  if (!target) {
    refuse("Откройте подписку из бота заново.");
    return;
  }

  var scheme;

  try {
    /* URLSearchParams уже вернул раскодированное значение. */
    scheme = new URL(target).protocol.toLowerCase();
  } catch (error) {
    refuse("Откройте подписку из бота заново.");
    return;
  }

  if (FORBIDDEN_SCHEMES.indexOf(scheme) !== -1) {
    refuse("Эта ссылка ведёт не в приложение. Откройте подписку из бота заново.");
    return;
  }

  button.href = target;
  button.hidden = false;

  /*
   * replace, а не href: иначе кнопка «назад» возвращала бы на эту же
   * страницу, и она снова уводила бы в приложение.
   */
  try {
    window.location.replace(target);
  } catch (error) {
    window.location.href = target;
  }
})();
