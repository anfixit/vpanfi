/*
 * Открывает приложение по ссылке, которую передал бот.
 *
 * Приложение — не наше: человек ставит Happ, V2RayTun, Streisand или любое
 * другое, умеющее принять ссылку на подписку. Бот кладёт в параметр
 * redirect_to его адрес — happ://add/…, v2raytun://import/…,
 * sing-box://import-remote-profile?url=… Такой адрес нельзя положить в
 * кнопку Telegram, поэтому он приезжает сюда.
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

  /*
   * Схема ссылки называет приложение, и назвать его человеку полезнее, чем
   * писать «приложение»: он видит, что откроется именно тот Happ, который
   * он ставил. Список неполный намеренно — приложения в панели меняются, и
   * незнакомая схема просто останется безымянной, а не сломает страницу.
   */
  var APP_NAMES = {
    "happ:": "Happ",
    "v2raytun:": "V2RayTun",
    "v2rayng:": "v2rayNG",
    "v2box:": "V2Box",
    "streisand:": "Streisand",
    "shadowrocket:": "Shadowrocket",
    "hiddify:": "Hiddify",
    "sing-box:": "sing-box",
    "clash:": "Clash",
    "clashmeta:": "Clash Meta",
    "nekobox:": "NekoBox",
    "karing:": "Karing",
    "flclash:": "FlClash",
  };

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

  var appName = APP_NAMES[scheme];

  if (appName) {
    title.textContent = "Открываем " + appName + "…";
    /*
     * Без местоимения: имена приложений разного рода, и «он не открылся»
     * рядом с sing-box или Karing читается неряшливо.
     */
    hint.textContent =
      "Подписка добавится в " + appName + " сама. Если приложение не открылось — нажмите кнопку ниже.";
    button.textContent = "Открыть " + appName;
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
