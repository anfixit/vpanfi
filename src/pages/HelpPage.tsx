import { useEffect, useRef, useState, type ReactNode } from "react";
import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { maxSupportUrl, supportEmail, telegramSupportUrl } from "../config";
import "../help.css";

type Platform = "ios" | "android" | "windows";
type Mode = "trouble" | "setup";
const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "ios", label: "iPhone и iPad" },
  { id: "android", label: "Android" },
  { id: "windows", label: "Windows" },
];
const APP_INCY = "https://apps.apple.com/ru/app/incy/id6756943388";
const APP_HAPP_ANDROID =
  "https://play.google.com/store/apps/details?id=com.happproxy";
const APP_HAPP_APK =
  "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk";
const APP_HAPP_WINDOWS =
  "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe";
const IOS_SOURCE = "https://protonvpn.com/support/ios-vpn-configurations";
const WINDOWS_SOURCE =
  "https://support.microsoft.com/en-us/windows/experience/connectivity-networking/connect-to-a-vpn-in-windows";
const PROXY_SOURCE = "https://protonvpn.com/support/windows-vpn-issues";

function readPlatform(): Platform {
  if (typeof window === "undefined") return "ios";
  const query = new URLSearchParams(window.location.search).get("device");
  if (PLATFORMS.some((p) => p.id === query)) return query as Platform;
  try {
    const saved = localStorage.getItem("vpanfi-help-platform");
    if (saved === "ios" || saved === "android" || saved === "windows")
      return saved;
  } catch {
    /* The guide also works without browser storage. */
  }
  if (/Android/i.test(navigator.userAgent)) return "android";
  if (/Windows/i.test(navigator.userAgent)) return "windows";
  return "ios";
}

function Shot({
  src,
  caption,
  source,
  sourceName = "Proton VPN",
  wide = false,
}: {
  src: string;
  caption: string;
  source: string;
  sourceName?: string;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <figure className={`help-shot${wide ? " help-shot-wide" : ""}`}>
      <button
        type="button"
        className="help-shot-open"
        onClick={() => dialog.current?.showModal()}
        aria-label={`Увеличить: ${caption}`}
      >
        <img src={`/help-images/${src}`} alt={caption} loading="lazy" />
        <span>Увеличить скриншот ↗</span>
      </button>
      <figcaption>
        {caption}{" "}
        <a href={source} target="_blank" rel="noreferrer">
          Источник: {sourceName}
        </a>
      </figcaption>
      <dialog
        ref={dialog}
        className="help-image-dialog"
        aria-label={caption}
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current.close();
        }}
      >
        <button
          type="button"
          className="button button-ghost"
          onClick={() => dialog.current?.close()}
          autoFocus
        >
          Закрыть ×
        </button>
        <img src={`/help-images/${src}`} alt={caption} loading="lazy" />
        <p>{caption}</p>
        <a href={`/help-images/${src}`} target="_blank" rel="noreferrer">
          Открыть оригинал в отдельной вкладке ↗
        </a>
      </dialog>
    </figure>
  );
}

function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <li className="help-step">
      <span className="help-step-number" aria-hidden="true">
        {n}
      </span>
      <div className="help-step-body">
        <h3>{title}</h3>
        {children}
      </div>
    </li>
  );
}
function Notice({ children }: { children: ReactNode }) {
  return <div className="help-note">{children}</div>;
}

function CleanIos() {
  return (
    <>
      <p>
        Удалите{" "}
        <strong>
          все старые VPN-подключения, которыми больше не пользуетесь
        </strong>
        : от прежних сервисов, пробных приложений и старых установок. Сначала
        сохраните актуальную ссылку VPaNfi из письма, бота или кабинета.
      </p>
      <Notice>
        <strong>Что оставить:</strong> текущую конфигурацию incy или Happ для
        VPaNfi.{" "}
        <strong>Уже установленный Happ не удаляйте и не сгружайте:</strong>{" "}
        сейчас его нет в российском App Store, повторная установка может быть
        недоступна. Рабочие, учебные профили и «Управление устройством» не
        удаляйте. Если название незнакомо, пришлите скриншот в поддержку.
      </Notice>
      <ol className="help-cleanup-list">
        <li>
          <strong>Отключите старый VPN в его приложении.</strong> Если он
          включается снова сам, отключите автоподключение в этом приложении.
        </li>
        <li>
          <strong>Откройте настройки iPhone.</strong> Перейдите:{" "}
          <span className="help-path">
            Настройки → Основные → VPN и управление устройством → VPN
          </span>
          . Если не находите пункт, в поиске настроек введите «VPN».
        </li>
        <li>
          <strong>Нажмите ⓘ справа от старого подключения.</strong> Нужна
          маленькая буква «i» в круге, а не общий переключатель VPN.
        </li>
        <li>
          <strong>
            Отключите «Подключение по требованию», если этот пункт есть.
          </strong>{" "}
          Затем нажмите <strong>«Удалить VPN»</strong> и подтвердите. Повторите
          для каждого ненужного подключения.
        </li>
      </ol>
      <div className="help-shots-row">
        <Shot
          src="ios-vpn-list.png"
          caption="1. Кнопка ⓘ открывает настройки выбранного VPN."
          source={IOS_SOURCE}
        />
        <Shot
          src="ios-delete-vpn.png"
          caption="2. Connect On Demand — подключение по требованию. Delete VPN — «Удалить VPN»."
          source={IOS_SOURCE}
        />
      </div>
      <p className="help-image-context">
        На скриншотах — системные экраны iPhone на примере старого Proton VPN. У
        Вас будет название Вашего приложения. Устанавливать Proton VPN для этих
        шагов не нужно.
      </p>
      <ol className="help-cleanup-list" start={5}>
        <li>
          <strong>Проверьте отдельно скачанные профили.</strong> Вернитесь в
          «VPN и управление устройством». Если ниже VPN есть профиль от прежнего
          личного VPN-сервиса, откройте его, проверьте название и содержимое,
          затем выберите «Удалить профиль». iPhone может запросить код-пароль.
          Удаление такого профиля удаляет и связанные с ним настройки;
          корпоративный профиль сюда не относится. Если профилей нет —
          пропустите шаг.
        </li>
        <li>
          <strong>Удалите ненужное VPN-приложение.</strong> Удерживайте его
          значок → «Удалить приложение» → подтвердите удаление. «Убрать с экрана
          Домой» только прячет значок. Если приложение нужно для других задач —
          оставьте его отключённым.
        </li>
        <li>
          <strong>Перезагрузите iPhone.</strong> Откройте выбранный incy или
          Happ и включите VPaNfi. Если появится запрос на добавление
          конфигурации именно этого приложения — нажмите «Разрешить».
        </li>
      </ol>
      <details className="help-detail">
        <summary>Старый профиль возвращается или кнопки удаления нет</summary>
        <p>
          Его может создавать оставшееся VPN-приложение или система управления
          устройством. Проверьте автоподключение старого приложения. Для
          рабочего или учебного iPhone обратитесь к администратору. Не удаляйте
          управление устройством и не сбрасывайте iPhone — пришлите нам экран,
          на котором остановились.
        </p>
      </details>
      <p className="help-source-note">
        <a
          href="https://support.apple.com/ru-ru/guide/iphone/iph6c493b19/ios"
          target="_blank"
          rel="noreferrer"
        >
          Apple: как удалить профиль конфигурации
        </a>
      </p>
    </>
  );
}

function CleanWindows() {
  return (
    <>
      <p>
        На Windows старый VPN может остаться <strong>в трёх местах</strong>: в
        списке подключений, в установленной программе и в настройках прокси.
        Проверим каждое. Сохраните актуальную ссылку VPaNfi до удаления старых
        записей.
      </p>
      <Notice>
        Удаляйте все подключения и программы{" "}
        <strong>от VPN, которыми больше не пользуетесь</strong>. Текущий Happ и
        рабочий VPN оставьте. На компьютере организации сетевые настройки
        согласуйте с её администратором.
      </Notice>
      <ol className="help-cleanup-list">
        <li>
          <strong>Полностью закройте старые VPN-программы.</strong> Справа
          внизу, около часов, нажмите стрелку ∧. Нажмите правой кнопкой на
          значок старого VPN → «Отключить», затем «Выход» / Exit / Quit. Крестик
          окна часто лишь сворачивает программу.
        </li>
        <li>
          <strong>Отключите их автоподключение.</strong> Если старое приложение
          запрещает интернет без своего VPN («Kill switch», «Блокировать без
          VPN»), выключите эту функцию в нём перед удалением. Защиту Windows и
          антивирус отключать не нужно.
        </li>
        <li>
          <strong>Откройте список VPN.</strong> Нажмите <kbd>Win</kbd> +{" "}
          <kbd>I</kbd> →{" "}
          <span className="help-path">Сеть и Интернет → VPN</span>. Найдите
          старое подключение по названию сервиса.
        </li>
        <li>
          <strong>Удалите каждую ненужную запись.</strong> В Windows 11
          раскройте её стрелкой справа; в Windows 10 нажмите на название. Если
          подключение активно — сначала «Отключиться». Затем{" "}
          <strong>«Удалить» → подтвердить</strong>. Пустой список — нормально:
          Happ и некоторые другие приложения не создают здесь обычных
          подключений. Не нажимайте «Добавить VPN» для настройки VPaNfi.
        </li>
      </ol>
      <Shot
        src="windows-delete-vpn.png"
        caption="Windows 11: раскройте старое подключение и нажмите Remove — «Удалить». Название у Вас будет другим."
        source="https://cc.kmutt.ac.th/Files/VPN/VPN_Manual_update202510/Windows%2011/Manual%20setup%20VPN%20Windows%2011.pdf"
        sourceName="инструкция IT-службы KMUTT"
        wide
      />
      <ol className="help-cleanup-list" start={5}>
        <li>
          <strong>Удалите старые VPN-программы.</strong> Windows 11: «Параметры
          → Приложения → Установленные приложения → ⋯ рядом с программой →
          Удалить». Windows 10: «Приложения → Приложения и возможности →
          название → Удалить». Выполните шаги штатного удаления. Если VPN нужен
          для работы, оставьте программу и отключите её автозапуск.
        </li>
        <li>
          <strong>Проверьте расширения браузера.</strong> В меню Chrome или Edge
          откройте «Расширения → Управление расширениями». Отключите расширения
          прежних VPN/прокси. Это отдельные настройки, они могут остаться после
          удаления приложения.
        </li>
        <li>
          <strong>Перезагрузите компьютер.</strong> После загрузки откройте
          только Happ, обновите VPaNfi и подключитесь. Проверьте два сайта в
          браузере.
        </li>
      </ol>
      <details className="help-detail">
        <summary>
          После удаления старого VPN браузер всё ещё без интернета: проверьте
          прокси
        </summary>
        <p>
          Сначала отключите VPN и закройте Happ. Перейдите в «Параметры → Сеть и
          Интернет → Прокси-сервер». Если ручной прокси или сценарий настройки
          остался от удалённого личного VPN, выключите именно его. Если видите
          кнопку «Сохранить» / Save, нажмите её.
        </p>
        <p>
          В Windows 11: «Использовать прокси-сервер → Изменить → Выкл. →
          Сохранить». В Windows 10 — переключатель «Использовать прокси-сервер».
          Настройку «Использовать сценарий настройки» отключайте только если она
          принадлежала старому VPN. Если адрес назначила организация или Вы не
          знаете его назначение — пришлите скриншот в поддержку.
        </p>
        <Shot
          src="windows-proxy.png"
          caption="Прокси-сервер Windows 11: Use a proxy server — «Использовать прокси-сервер», Edit — «Изменить»."
          source={PROXY_SOURCE}
          wide
        />
        <p>
          Откройте браузер заново, затем включите Happ. Не удаляйте сетевые
          адаптеры, драйверы и не выполняйте «Сброс сети» — для этих шагов они
          не нужны.
        </p>
      </details>
      <p className="help-source-note">
        <a href={WINDOWS_SOURCE} target="_blank" rel="noreferrer">
          Microsoft: где находятся настройки VPN
        </a>
      </p>
    </>
  );
}

function CleanAndroid() {
  return (
    <>
      <p>
        Отключите старый VPN в его приложении. Затем найдите в настройках
        телефона «VPN». Обычно путь такой:{" "}
        <span className="help-path">Настройки → Сеть и интернет → VPN</span>. На
        Samsung: «Подключения → Другие настройки соединения → VPN».
      </p>
      <ol className="help-cleanup-list">
        <li>
          Нажмите шестерёнку около старого VPN. Отключите «Постоянная VPN» /
          Always-on VPN и «Блокировать соединения без VPN», если они включены
          для старого приложения.
        </li>
        <li>
          Выберите «Удалить VPN» / «Забыть VPN», если такая кнопка есть. Удалите
          все ненужные старые подключения. Рабочий профиль организации оставьте.
        </li>
        <li>
          В «Настройки → Приложения» удалите прежние VPN-приложения, которыми
          больше не пользуетесь. Если список VPN пуст, всё равно проверьте
          приложения.
        </li>
        <li>
          Перезагрузите телефон. Откройте Happ, обновите подписку VPaNfi и
          подключитесь. Подтвердите системный запрос на VPN.
        </li>
      </ol>
      <Notice>
        Названия пунктов зависят от производителя. Если не находите нужный
        экран, напишите модель телефона — подскажем путь для него.
      </Notice>
    </>
  );
}

function Cleanup({ platform }: { platform: Platform }) {
  return platform === "ios" ? (
    <CleanIos />
  ) : platform === "windows" ? (
    <CleanWindows />
  ) : (
    <CleanAndroid />
  );
}
function RefreshGuide() {
  return (
    <>
      <p>
        Откройте incy или Happ. Найдите <strong>профиль VPaNfi</strong> — группу
        с Вашими серверами. Нажмите круглую стрелку обновления рядом с группой
        либо откройте её меню → «Обновить подписку». Дождитесь окончания
        обновления, выберите сервер и подключитесь снова.
      </p>
      <p>
        Не нужно покупать подписку повторно. Если мы прислали Вам новую ссылку,
        сохраните её, удалите из приложения старую группу VPaNfi и добавьте
        новую ссылку целиком. При нескольких копиях оставьте одну актуальную.
      </p>
      <Notice>
        Профиль VPaNfi <strong>в приложении</strong> — это список серверов.
        Конфигурация VPN <strong>в настройках телефона</strong> — разрешение
        приложению подключаться. Это разные записи: обновление списка не удаляет
        настройки старого VPN.
      </Notice>
    </>
  );
}

function Troubleshooting({ platform }: { platform: Platform }) {
  return (
    <section
      id="trouble"
      className="help-content-section"
      aria-labelledby="trouble-title"
    >
      <div className="help-section-heading">
        <span className="section-kicker">Вернём подключение по шагам</span>
        <h2 id="trouble-title">VPN не работает?</h2>
        <p>
          После каждого шага попробуйте открыть сайт. Заработало — дальше ничего
          менять не нужно.
        </p>
      </div>
      <ol className="help-steps">
        <Step n={1} title="Проверьте интернет без VPN">
          <p>
            Отключите VPN и откройте сайт, который обычно доступен без него.
            Если он тоже не открывается, попробуйте другую сеть: Wi-Fi вместо
            мобильного интернета или наоборот. На компьютере можно проверить
            подключение через точку доступа телефона.
          </p>
          <p>
            В гостинице или общественном Wi-Fi сначала может понадобиться войти
            в сеть через страницу приветствия.
          </p>
        </Step>
        <Step n={2} title="Обновите VPaNfi и попробуйте другой сервер">
          <RefreshGuide />
          <p>
            Попробуйте другую страну. Затем переключите вариант с 🌐 на 🛜 или
            наоборот. Подписи «лучше с мобильного» и «лучше с Wi-Fi и ПК»
            помогают начать выбор, но не гарантируют работу в конкретной сети.
          </p>
        </Step>
        <Step n={3} title="Уберите старые VPN-профили">
          <p>
            Старый VPN, его автоподключение или прокси могут мешать новому. Само
            наличие старой записи ещё не доказывает причину сбоя. Если первые
            шаги не помогли, очистите ненужные подключения по инструкции для
            Вашего устройства.
          </p>
          <details className="help-detail help-detail-important" open>
            <summary>
              Пошагово: {PLATFORMS.find((p) => p.id === platform)?.label}
            </summary>
            <div className="help-detail-body">
              <Cleanup platform={platform} />
            </div>
          </details>
        </Step>
        <Step n={4} title="Перезапустите приложение и проверьте результат">
          <p>
            {platform === "ios"
              ? "Если для Вашего приложения доступно обновление в App Store, установите его. Уже установленный Happ сохраняйте: сейчас его нет в российском магазине. "
              : "Обновите приложение по официальной ссылке из раздела «Подключить впервые». "}
            Полностью закройте приложение и откройте снова. Включите VPN и
            проверьте два разных сайта, затем видео или приложение, ради
            которого подключались.
          </p>
          <p>
            <strong>
              Значок VPN сам по себе не означает, что интернет работает.
            </strong>{" "}
            Если значок есть, а сайты не открываются — напишите нам, на каком
            шаге остановились. Не тратьте время на бесконечную переустановку.
          </p>
        </Step>
      </ol>
      <div className="help-section-heading help-errors-heading">
        <h2>Вижу конкретную проблему</h2>
      </div>
      <details className="help-detail">
        <summary>«Лимит устройств» — даже на моём старом телефоне</summary>
        <p>
          После переустановки приложение иногда распознаётся как новое
          устройство. В кабинете откройте «Устройства» и проверьте список.
          Удалите привязку только того устройства или старой установки, которыми
          больше не пользуетесь, затем обновите VPaNfi. Если записи одинаковые
          или Вы не можете войти, пришлите их скриншот в поддержку. Удаление
          VPN-профиля в настройках телефона само по себе место в подписке не
          освобождает.
        </p>
      </details>
      <details className="help-detail">
        <summary>«Подписка истекла», хотя я заплатил(а)</summary>
        <p>
          Сверьте срок в кабинете и обновите подписку в приложении. Пополнение
          баланса в боте и покупка подписки могут быть разными действиями:
          проверьте, оформлено ли продление. Если оплата прошла, а срок не
          изменился, пришлите дату, сумму и номер операции. Не оплачивайте
          повторно, пока мы проверяем.
        </p>
      </details>
      <details className="help-detail">
        <summary>«Приложение не поддерживается» или серверов нет</summary>
        <p>
          Убедитесь, что используете актуальный incy или Happ по ссылкам на этой
          странице. Скопируйте ссылку целиком, без пробелов и обрезанного конца,
          и обновите подписку. Если сообщение осталось — пришлите название и
          версию приложения и текст ошибки. Это может быть проблема формата
          выдачи, её нужно проверить с нашей стороны.
        </p>
      </details>
      <details className="help-detail">
        <summary>VPN включён, но не открывается только часть сайтов</summary>
        <p>
          Проверьте второй сайт, другую страну и другую сеть. Полностью
          перезапустите браузер. На Windows проверьте старые прокси и
          VPN-расширения по инструкции выше. На телефоне сообщите, используете
          ли отдельный блокировщик рекламы или приложение для DNS. Не отключайте
          защиту устройства наугад — пришлите названия неработающих сайтов и
          текст ошибки.
        </p>
      </details>
      <details className="help-detail">
        <summary>
          Работает медленно или отключается при блокировке экрана
        </summary>
        <p>
          Попробуйте другую страну и сравните Wi-Fi с мобильным интернетом. Если
          на Android связь пропадает именно после блокировки экрана, откройте
          «Настройки → Приложения → Happ → Батарея» и разрешите работу в фоне; у
          разных производителей пункт называется по-разному. Если обрывы
          остаются, укажите время и сеть в сообщении поддержке.
        </p>
      </details>
    </section>
  );
}

function Setup({ platform }: { platform: Platform }) {
  const ios = platform === "ios";
  const app = ios ? "incy" : "Happ";
  return (
    <section
      id="setup"
      className="help-content-section"
      aria-labelledby="setup-title"
    >
      <div className="help-section-heading">
        <span className="section-kicker">Первое подключение</span>
        <h2 id="setup-title">
          Настроим {PLATFORMS.find((p) => p.id === platform)?.label}
        </h2>
        <p>
          Понадобится актуальная ссылка VPaNfi из письма после покупки, бота или
          личного кабинета. Не публикуйте её: она даёт доступ к Вашей подписке.
        </p>
      </div>
      <ol className="help-steps">
        <Step n={1} title={`Установите ${app} по официальной ссылке`}>
          {ios ? (
            <>
              <p>
                Установите <strong>incy</strong>, разработчик{" "}
                <strong>LLC ITDEV</strong>. Оно доступно в российском App Store.
                Откройте магазин по кнопке — искать приложение по похожему
                названию не нужно.
              </p>
              <a
                className="button button-primary"
                href={APP_INCY}
                target="_blank"
                rel="noreferrer"
              >
                incy в App Store ↗
              </a>
              <Notice>
                <strong>Happ нет в российском App Store.</strong> Проверено 5
                сентября 2026. Если Happ уже установлен, оставьте его: удалять
                или сгружать приложение для переустановки не нужно. Для нового
                подключения используйте incy по кнопке выше. Если магазин пишет
                «Недоступно», пришлите этот экран в поддержку.
              </Notice>
            </>
          ) : platform === "android" ? (
            <>
              <a
                className="button button-primary"
                href={APP_HAPP_ANDROID}
                target="_blank"
                rel="noreferrer"
              >
                Happ в Google Play ↗
              </a>
              <p>
                Если Google Play недоступен,{" "}
                <a href={APP_HAPP_APK} target="_blank" rel="noreferrer">
                  скачайте APK из репозитория разработчика
                </a>
                . Разрешите установку этому источнику только на время установки,
                затем отключите разрешение.
              </p>
            </>
          ) : (
            <>
              <a
                className="button button-primary"
                href={APP_HAPP_WINDOWS}
                target="_blank"
                rel="noreferrer"
              >
                Скачать Happ для Windows ↗
              </a>
              <p>
                Это установщик для Windows x64. Запустите скачанный файл и
                выполните шаги установки. Если Windows или антивирус блокирует
                его, не отключайте защиту: проверьте, что файл скачан по этой
                ссылке, и пришлите нам текст предупреждения. Для ARM-компьютера
                напишите в поддержку.
              </p>
            </>
          )}
        </Step>
        <Step n={2} title="Скопируйте актуальную ссылку VPaNfi">
          <p>
            В <a href={routes.connect}>кабинете → «Подключить»</a> нажмите
            кнопку копирования. Если ссылка в письме или боте:{" "}
            {platform === "windows"
              ? "выделите её полностью и нажмите Ctrl+C"
              : "удерживайте ссылку и выберите «Скопировать ссылку»"}
            . Копируйте весь адрес, от https:// до конца.
          </p>
          <p>
            Ссылка выглядит длинной — это нормально. Не нужно переписывать её
            вручную, покупать что-то внутри приложения или создавать новый
            аккаунт ради подключения.
          </p>
        </Step>
        <Step n={3} title={`Добавьте подписку в ${app}`}>
          <p>
            Откройте {app}, нажмите «+» и выберите добавление из буфера обмена.
            Если телефон спрашивает разрешение вставить скопированное —
            разрешите. Название пункта может быть «Вставить из буфера обмена»
            или «Импорт из буфера обмена».
          </p>
          <Notice>
            <strong>Что должно получиться:</strong> появилась группа VPaNfi со
            списком серверов или стран. Если список пуст или есть ошибка, не
            переходите к подключению — откройте раздел «VPN не работает».
          </Notice>
        </Step>
        <Step n={4} title="Выберите сервер и включите VPN">
          <p>
            Начните с Германии или Нидерландов. Для мобильной сети попробуйте
            🌐, для Wi-Fi — 🛜. Нажмите кнопку подключения. Если вариант не
            работает, попробуйте второй значок или другую страну.
          </p>
          {ios ? (
            <>
              <p>
                При первом включении iPhone попросит добавить конфигурацию VPN.
                Проверьте название приложения в запросе, нажмите «Разрешить» и
                подтвердите действие способом, который предложит iPhone.
              </p>
              <Shot
                src="ios-permission.jpg"
                caption="Пример системного запроса iPhone: Allow — «Разрешить». В Вашем запросе должно быть имя incy или Happ."
                source={IOS_SOURCE}
              />
            </>
          ) : platform === "android" ? (
            <p>
              Android покажет системный запрос VPN. Проверьте, что он от Happ, и
              подтвердите. Если у Вас уже включён другой VPN, сначала отключите
              его.
            </p>
          ) : (
            <p>
              Если интернет работает только в браузере, но не в других
              программах, сообщите нам режим работы Happ и версию Windows:
              проверим настройку системного туннеля.
            </p>
          )}
        </Step>
        <Step n={5} title="Убедитесь, что всё действительно открывается">
          <p>
            Откройте два разных сайта, затем нужное видео или приложение. Значок
            VPN показывает включённое соединение, но окончательная проверка —
            загружающиеся страницы.
          </p>
          <Notice>
            <strong>Получилось?</strong> Оставьте один актуальный профиль
            VPaNfi. Если серверы позже перестанут отвечать, сначала обновите
            подписку в приложении.
          </Notice>
        </Step>
      </ol>
    </section>
  );
}

function Support({ platform }: { platform: Platform }) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const template = `Не работает VPaNfi.\nУстройство: ${PLATFORMS.find((p) => p.id === platform)?.label}\nМодель и версия системы: \nПриложение и его версия: \nСеть и оператор (Wi-Fi / мобильная): \nЧто вижу на экране: \nСервер / страна: \nКогда началось: \nУже попробовал(а): \nВ другой сети: \n`;
  return (
    <aside id="contact" className="help-contact">
      <Mascot variant="support" className="help-mascot" decorative />
      <span className="section-kicker">Можно сразу написать</span>
      <h2>Застряли? Помогу.</h2>
      <p>
        Не нужно разбираться во всём самостоятельно. Пришлите скриншот ошибки и
        скажите, на каком шаге остановились.
      </p>
      <a
        className="button button-primary"
        href={maxSupportUrl}
        target="_blank"
        rel="noreferrer"
      >
        Написать Анфисе в MAX ↗
      </a>
      <a
        className="button button-ghost"
        href={`mailto:${supportEmail}?subject=${encodeURIComponent("Не работает VPaNfi")}&body=${encodeURIComponent(template)}`}
      >
        Написать на почту
      </a>
      <p className="help-secondary">
        Если VPN не подключается, попробуйте MAX или почту.{" "}
        <a href={telegramSupportUrl} target="_blank" rel="noreferrer">
          Telegram
        </a>{" "}
        может быть недоступен в Вашей сети.
      </p>
      <details className="help-detail">
        <summary>Что написать, чтобы быстрее разобраться</summary>
        <p>Можно скопировать и заполнить этот шаблон:</p>
        <pre className="help-support-template">{template}</pre>
        <button
          className="button button-ghost"
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(template);
              setCopied(true);
              setCopyFailed(false);
            } catch {
              setCopyFailed(true);
            }
          }}
        >
          Скопировать шаблон
        </button>
        <p role="status">
          {copyFailed
            ? "Не удалось скопировать автоматически. Выделите текст выше и скопируйте вручную."
            : copied
              ? "Шаблон скопирован. Вставьте его в сообщение."
              : ""}
        </p>
      </details>
      <p className="help-secondary">
        На скриншоте скройте ссылку подписки и QR-код. Номер карты, пароль и
        коды из SMS не нужны.
      </p>
    </aside>
  );
}

export function HelpPage({
  theme,
  onToggleTheme,
}: {
  theme: Theme;
  onToggleTheme: () => void;
}) {
  const [platform, setPlatform] = useState<Platform>(readPlatform);
  const [mode, setMode] = useState<Mode>(() =>
    typeof window !== "undefined" && window.location.hash === "#setup"
      ? "setup"
      : "trouble",
  );
  useEffect(() => {
    try {
      localStorage.setItem("vpanfi-help-platform", platform);
    } catch {
      /* optional */
    }
  }, [platform]);
  useEffect(() => {
    const update = () => {
      if (
        window.location.hash === "#setup" ||
        window.location.hash === "#trouble"
      )
        setMode(window.location.hash === "#setup" ? "setup" : "trouble");
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  function selectMode(next: Mode) {
    setMode(next);
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${window.location.search}#${next}`,
    );
  }
  return (
    <>
      <header className="site-header help-site-header shell">
        <Brand />
        <div className="header-actions">
          <a className="help-header-contact" href="#contact">
            Связаться с Анфисой
          </a>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <a className="button button-ghost" href={routes.landing}>
            На главную
          </a>
        </div>
      </header>
      <main className="help-page shell">
        <section className="help-intro">
          <div>
            <span className="section-kicker">
              Помощь VPaNfi · без входа в аккаунт
            </span>
            <h1>
              Подключим.
              <br />
              <span>А если не работает — разберёмся.</span>
            </h1>
            <p>
              Выберите свою задачу и устройство. Всё по шагам, с подсказками,
              куда нажать.
            </p>
          </div>
          <Mascot variant="phone" className="help-hero-mascot" decorative />
        </section>
        <div className="help-entry-points" aria-label="С чем нужна помощь">
          <button
            type="button"
            className={`help-entry help-entry-trouble${mode === "trouble" ? " is-selected" : ""}`}
            aria-pressed={mode === "trouble"}
            onClick={() => selectMode("trouble")}
          >
            <span className="help-entry-icon" aria-hidden="true">
              !
            </span>
            <span>
              <strong>VPN не работает?</strong>
              <small>Не подключается, нет интернета или появился сбой</small>
            </span>
            <span aria-hidden="true">↓</span>
          </button>
          <button
            type="button"
            className={`help-entry${mode === "setup" ? " is-selected" : ""}`}
            aria-pressed={mode === "setup"}
            onClick={() => selectMode("setup")}
          >
            <span className="help-entry-icon" aria-hidden="true">
              +
            </span>
            <span>
              <strong>Подключить впервые</strong>
              <small>Установить приложение и добавить свою подписку</small>
            </span>
            <span aria-hidden="true">↓</span>
          </button>
        </div>
        <p className="help-quick-contact">
          Можно сразу обратиться за помощью:{" "}
          <a href={maxSupportUrl} target="_blank" rel="noreferrer">
            Анфиса в MAX ↗
          </a>{" "}
          <span aria-hidden="true">·</span>{" "}
          <a href={`mailto:${supportEmail}`}>Написать на почту</a>
        </p>
        <nav className="help-tabs" aria-label="Ваше устройство">
          {PLATFORMS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`help-tab${platform === p.id ? " help-tab-active" : ""}`}
              aria-pressed={platform === p.id}
              onClick={() => {
                setPlatform(p.id);
                document
                  .querySelector(".help-tabs")
                  ?.scrollIntoView({ block: "start" });
              }}
            >
              {p.label}
            </button>
          ))}
        </nav>
        <div className="help-layout">
          <div key={`${platform}-${mode}`} className="help-main-guide">
            {mode === "trouble" ? (
              <Troubleshooting platform={platform} />
            ) : (
              <Setup platform={platform} />
            )}
            <div className="help-switch-next">
              <p>
                {mode === "setup"
                  ? "На каком-то шаге не получилось?"
                  : "Нужна инструкция с самого начала?"}
              </p>
              <button
                className="button button-primary"
                type="button"
                onClick={() => {
                  selectMode(mode === "setup" ? "trouble" : "setup");
                  document
                    .querySelector(".help-tabs")
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                {mode === "setup"
                  ? "VPN не работает — проверить по шагам"
                  : "Перейти к первому подключению"}
              </button>
            </div>
          </div>
          <Support platform={platform} />
        </div>
        <footer className="help-footer">
          <p>
            Названия пунктов могут отличаться в разных версиях системы и
            приложения. Скриншоты можно увеличить; под каждым указан источник.
          </p>
          <p>
            Ссылки на приложения проверены 5 сентября 2026 года. Нужна помощь с
            другим устройством?{" "}
            <a href={maxSupportUrl} target="_blank" rel="noreferrer">
              Напишите Анфисе
            </a>
            .
          </p>
        </footer>
      </main>
    </>
  );
}
