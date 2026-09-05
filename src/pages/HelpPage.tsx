import { useEffect, useState } from "react";
import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { maxSupportUrl, supportEmail, telegramSupportUrl } from "../config";

/*
 * Страница помощи открыта всем и без входа: сюда приходит тот, у кого
 * как раз ничего не работает, и заставлять его входить в кабинет нельзя.
 *
 * Раздел «Не подключается» собран не из общих советов, а из причин,
 * которые мы нашли у живых людей в сентябре 2026: другой VPN, включённый
 * на том же устройстве; офисная сеть, режущая нестандартный порт;
 * старая ссылка, оставшаяся в приложении; приложение без поддержки
 * устройств. Порядок пунктов это порядок частоты.
 */

const APP_INCY = "https://apps.apple.com/ru/app/incy/id6756943388";
const APP_HAPP_IOS = "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215";
const APP_HAPP_ANDROID = "https://play.google.com/store/apps/details?id=com.happproxy";
const APP_HAPP_APK =
  "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk";
const APP_HAPP_WINDOWS =
  "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe";

type Platform = "ios" | "android" | "windows" | "router";

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "ios", label: "iPhone и iPad" },
  { id: "android", label: "Android" },
  { id: "windows", label: "Windows" },
  { id: "router", label: "Роутер" },
];

const STORAGE_KEY = "vpanfi-help-platform";

function readPlatform(): Platform {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "ios" || saved === "android" || saved === "windows" || saved === "router") {
      return saved;
    }
  } catch {
    // Хранилище может быть недоступно, тогда просто iPhone по умолчанию.
  }
  return "ios";
}

/*
 * Место под скриншот. Пока картинки нет, показывается подпись, что здесь
 * будет: страница читается и без иллюстраций, а не разваливается.
 */
function Shot({ src, caption }: { src: string; caption: string }) {
  const [missing, setMissing] = useState(false);
  return (
    <figure className="help-shot">
      {missing ? (
        <div className="help-shot-placeholder" aria-hidden="true">
          {caption}
        </div>
      ) : (
        <img
          src={`/help/${src}`}
          alt={caption}
          loading="lazy"
          onError={() => setMissing(true)}
        />
      )}
      <figcaption>{caption}</figcaption>
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
  children: React.ReactNode;
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

function IosGuide() {
  return (
    <>
      <p className="help-lead">
        В российском App Store настоящего Happ нет, там только подделки с
        похожими названиями. Поэтому для iPhone я рекомендую <strong>incy</strong>:
        он есть в российском магазине и у моих пользователей ни разу не подвёл.
        Если у Вас зарубежный App Store, подойдёт и Happ.
      </p>
      <ol className="help-steps">
        <Step n={1} title="Установите incy">
          <p>
            Откройте{" "}
            <a href={APP_INCY} target="_blank" rel="noreferrer">
              incy в App Store
            </a>{" "}
            и нажмите «Загрузить». Приложение бесплатное, регистрации не требует.
          </p>
          <Shot src="ios-01-appstore.png" caption="incy в App Store: кнопка «Загрузить»" />
        </Step>
        <Step n={2} title="Скопируйте ссылку на подписку">
          <p>
            Ссылка пришла Вам письмом после оплаты и лежит в кабинете на сайте.
            Нажмите на неё и удерживайте, пока не появится «Скопировать».
            Ссылку надо копировать <strong>целиком</strong>, вручную её не набирают.
          </p>
          <Shot src="ios-02-copy.png" caption="Долгое нажатие на ссылку, затем «Скопировать»" />
        </Step>
        <Step n={3} title="Добавьте подписку в incy">
          <p>
            Откройте incy, нажмите «+» в правом верхнем углу и выберите
            «Вставить из буфера обмена». Приложение само найдёт ссылку и
            добавит все серверы списком.
          </p>
          <Shot src="ios-03-paste.png" caption="Плюс, затем «Вставить из буфера обмена»" />
        </Step>
        <Step n={4} title="Разрешите добавить конфигурацию VPN">
          <p>
            iPhone спросит разрешение добавить конфигурацию VPN. Нажмите
            «Разрешить» и подтвердите код-паролем или Face ID. Без этого шага
            приложение не сможет включить туннель.
          </p>
          <Shot src="ios-04-permission.png" caption="Системный запрос: «Разрешить»" />
        </Step>
        <Step n={5} title="Выберите сервер и подключитесь">
          <p>
            В списке выберите страну с пометкой 🌐, она для мобильного
            интернета, и нажмите большую кнопку подключения. Внутри каждой
            страны приложение само выбирает самый быстрый сервер.
          </p>
          <Shot src="ios-05-connect.png" caption="Список стран и кнопка подключения" />
        </Step>
        <Step n={6} title="Проверьте, что интернет открывается">
          <p>
            В строке состояния появится значок VPN. Откройте любой сайт,
            который раньше не открывался. Если всё работает, больше ничего
            делать не нужно: подписка обновляется сама.
          </p>
          <Shot src="ios-06-done.png" caption="Значок VPN в строке состояния" />
        </Step>
      </ol>
    </>
  );
}

function AndroidGuide() {
  return (
    <>
      <p className="help-lead">
        Для Android рекомендую <strong>Happ</strong>. Он есть в Google Play, а
        если Play недоступен, ставится напрямую файлом.
      </p>
      <ol className="help-steps">
        <Step n={1} title="Установите Happ">
          <p>
            Из{" "}
            <a href={APP_HAPP_ANDROID} target="_blank" rel="noreferrer">
              Google Play
            </a>{" "}
            или{" "}
            <a href={APP_HAPP_APK} target="_blank" rel="noreferrer">
              файлом напрямую
            </a>
            . Во втором случае телефон спросит разрешение устанавливать из
            неизвестных источников, это нормально для приложения не из Play.
          </p>
          <Shot src="android-01-install.png" caption="Happ в Google Play" />
        </Step>
        <Step n={2} title="Скопируйте ссылку на подписку">
          <p>
            Из письма или из кабинета. Удерживайте палец на ссылке и выберите
            «Копировать». Целиком, от <code>https://</code> до конца.
          </p>
          <Shot src="android-02-copy.png" caption="Выделение ссылки и «Копировать»" />
        </Step>
        <Step n={3} title="Добавьте подписку">
          <p>
            В Happ нажмите «+» и выберите «Вставить из буфера обмена».
            Появится профиль VPaNfi со списком стран.
          </p>
          <Shot src="android-03-paste.png" caption="«Вставить из буфера обмена»" />
        </Step>
        <Step n={4} title="Разрешите VPN-подключение">
          <p>
            Android покажет запрос на создание VPN-подключения. Нажмите «ОК».
            Это единственное системное разрешение, которое нужно приложению.
          </p>
          <Shot src="android-04-permission.png" caption="Запрос подключения: «ОК»" />
        </Step>
        <Step n={5} title="Выберите сервер и подключитесь">
          <p>
            Страна с пометкой 🌐 для мобильного интернета, с пометкой 🛜 для
            Wi-Fi. Нажмите на неё, затем на кнопку подключения.
          </p>
          <Shot src="android-05-connect.png" caption="Выбор страны и подключение" />
        </Step>
        <Step n={6} title="Отключите экономию батареи для Happ">
          <p>
            Иначе Android усыпит приложение через несколько минут и VPN отвалится
            сам по себе. Настройки → Приложения → Happ → Батарея → «Без
            ограничений». На Samsung пункт называется «Неограниченно».
          </p>
          <Shot src="android-06-battery.png" caption="Батарея → «Без ограничений»" />
        </Step>
        <Step n={7} title="Проверьте, что интернет открывается">
          <p>
            В строке состояния появится значок ключа или VPN. Откройте любой
            сайт, который раньше не открывался. Если всё работает, больше
            ничего делать не нужно: подписка обновляется сама.
          </p>
          <Shot src="android-07-done.png" caption="Значок VPN в строке состояния" />
        </Step>
      </ol>
    </>
  );
}

function WindowsGuide() {
  return (
    <>
      <p className="help-lead">
        Для Windows рекомендую <strong>Happ</strong>. Установщик один файл,
        никаких дополнительных программ не нужно.
      </p>
      <ol className="help-steps">
        <Step n={1} title="Скачайте и установите Happ">
          <p>
            <a href={APP_HAPP_WINDOWS} target="_blank" rel="noreferrer">
              Скачать установщик
            </a>
            . Запустите его. Если Windows покажет синее окно «Защитник
            SmartScreen», нажмите «Подробнее», затем «Выполнить в любом случае».
            Так Windows встречает любую программу без дорогой подписи, это не
            признак вируса.
          </p>
          <Shot src="windows-01-install.png" caption="Окно SmartScreen: «Подробнее» → «Выполнить в любом случае»" />
        </Step>
        <Step n={2} title="Скопируйте ссылку на подписку">
          <p>
            Из письма или кабинета. Выделите ссылку целиком и нажмите Ctrl+C.
          </p>
          <Shot src="windows-02-copy.png" caption="Ссылка выделена, Ctrl+C" />
        </Step>
        <Step n={3} title="Добавьте подписку">
          <p>
            В Happ нажмите «+» и выберите «Вставить из буфера обмена».
          </p>
          <Shot src="windows-03-paste.png" caption="«Вставить из буфера обмена»" />
        </Step>
        <Step n={4} title="Подключитесь">
          <p>
            Выберите страну с пометкой 🛜, она рассчитана на Wi-Fi и компьютер,
            и нажмите кнопку подключения. При первом запуске Windows может
            спросить разрешение для брандмауэра, нажмите «Разрешить».
          </p>
          <Shot src="windows-04-connect.png" caption="Выбор страны и подключение" />
        </Step>
        <Step n={5} title="Проверьте, что нет другого VPN">
          <p>
            Параметры → Сеть и Интернет → VPN. Если там есть старые подключения
            от других программ, удалите их. Два VPN одновременно мешают друг
            другу, и это самая частая причина, по которой «ничего не работает».
          </p>
          <Shot src="windows-05-vpn-settings.png" caption="Параметры → Сеть и Интернет → VPN" />
        </Step>
        <Step n={6} title="Проверьте, что интернет открывается">
          <p>
            Откройте в браузере любой сайт, который раньше не открывался.
            Если он загрузился, всё готово. Если нет, закройте браузер
            полностью и откройте заново: некоторые браузеры держат старые
            соединения и не замечают, что VPN уже включён.
          </p>
          <Shot src="windows-06-done.png" caption="Happ в трее, сайт открывается" />
        </Step>
      </ol>
    </>
  );
}

function RouterGuide() {
  return (
    <>
      <p className="help-lead">
        На роутере подписка ставится один раз, и дальше VPN получают все
        устройства дома без установки приложений. Работает на роутерах с
        OpenWrt и прошивками на его основе.
      </p>
      <ol className="help-steps">
        <Step n={1} title="Вставьте ту же ссылку">
          <p>
            Ссылка одна на все устройства. В настройках роутера, в разделе
            подписок VPN, вставьте её целиком. Роутер получит список серверов
            в своём формате, отличном от телефонного, это нормально.
          </p>
        </Step>
        <Step n={2} title="Выберите сервер вручную">
          <p>
            На роутере автоматического выбора внутри страны нет, серверы
            перечислены по одному. Выберите любой из своей страны. Если он
            перестал отвечать, переключитесь на соседний.
          </p>
        </Step>
        <Step n={3} title="Правила по именам серверов">
          <p>
            Если Вы настроили на роутере правила, привязанные к именам
            серверов, они продолжают работать: названия серверов для роутеров
            я не меняла и менять не буду.
          </p>
        </Step>
      </ol>
      <p className="help-note">
        Подробная настройка зависит от прошивки. Если застряли, напишите мне,
        разберём на Вашем роутере.
      </p>
    </>
  );
}

function Troubleshooting() {
  return (
    <section className="help-trouble" id="trouble">
      <div className="section-heading compact-heading">
        <div>
          <span className="section-kicker">Проверяйте по порядку</span>
          <h2>Не подключается</h2>
        </div>
        <Mascot variant="error" className="help-mascot" decorative />
      </div>
      <p className="help-lead">
        Эти причины я нашла у реальных людей, а не выдумала. Первая встречается
        чаще всех, поэтому начните с неё, даже если уверены, что дело не в ней.
      </p>

      <ol className="help-causes">
        <li>
          <h3>На устройстве включён другой VPN</h3>
          <p>
            Самая частая причина. Два VPN одновременно не работают: туннель VPaNfi
            пытается подняться внутри чужого и умирает. Вы могли давно забыть
            про старое приложение, но его профиль остался в системе и
            перехватывает трафик.
          </p>
          <ul>
            <li>
              <strong>iPhone:</strong> Настройки → Основные → VPN и управление
              устройством → VPN. Удалите всё, кроме incy или Happ. Затем
              Настройки → Основные → VPN и управление устройством → профили:
              удалите профили других VPN, если есть.
            </li>
            <li>
              <strong>Android:</strong> Настройки → Сеть и интернет → VPN.
              Отключите и удалите все чужие. Проверьте также «Частный DNS», он
              должен быть выключен или «Автоматически».
            </li>
            <li>
              <strong>Windows:</strong> Параметры → Сеть и Интернет → VPN.
              Удалите чужие подключения и выйдите из других VPN-программ в
              трее.
            </li>
          </ul>
        </li>

        <li>
          <h3>Вы в офисной, гостиничной или ограниченной сети</h3>
          <p>
            Такие сети часто пропускают только обычные веб-порты. Серверы с
            пометкой 🌐 используют нестандартный порт и в такой сети молчат.
            <strong> Выберите сервер с пометкой 🛜</strong>, он идёт по
            стандартному порту 443 и проходит почти везде. Или переключитесь
            на мобильный интернет.
          </p>
        </li>

        <li>
          <h3>В приложении осталась старая ссылка</h3>
          <p>
            Если Вам когда-то выдавали новую ссылку, старая продолжает
            обновляться и мешать. Удалите в приложении все профили VPaNfi
            и добавьте актуальную ссылку заново. Актуальная всегда лежит в
            кабинете на сайте.
          </p>
        </li>

        <li>
          <h3>Обновите подписку</h3>
          <p>
            В приложении у профиля VPaNfi есть кнопка обновления, стрелка по
            кругу. Нажмите её: список серверов подтянется заново. Это лечит
            случаи, когда серверы менялись, а приложение ещё не узнало.
          </p>
        </li>

        <li>
          <h3>Приложение написало «Приложение не поддерживается»</h3>
          <p>
            Значит, Вы открыли ссылку в приложении, которое не умеет
            представляться серверу VPaNfi. Поставьте incy или Happ по
            инструкции выше. Другие приложения работать не будут.
          </p>
        </li>

        <li>
          <h3>Вы поставили Happ из российского App Store</h3>
          <p>
            Настоящего Happ там нет. Всё, что находится по этому слову в
            российском магазине, подделки под чужим именем. Удалите и
            поставьте incy.
          </p>
        </li>

        <li>
          <h3>Подключается, но интернет не работает</h3>
          <p>
            Значок VPN есть, а сайты не открываются. Чаще всего это первая
            причина из списка, другой VPN. Если его точно нет, переключите
            страну: с 🌐 на 🛜 или наоборот, они устроены по-разному.
          </p>
        </li>

        <li>
          <h3>Работает, но медленно</h3>
          <p>
            Попробуйте другую страну. Скорость зависит от Вашего провайдера и
            маршрута до сервера, и для одного человека быстрее Германия, для
            другого Нидерланды. Внутри страны приложение уже само держит
            быстрейший сервер.
          </p>
        </li>
      </ol>
    </section>
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

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, platform);
    } catch {
      // Не смогли запомнить выбор, страница от этого не страдает.
    }
  }, [platform]);

  return (
    <>
      <header className="site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button
            className="button button-ghost"
            type="button"
            onClick={() => navigate(routes.landing)}
          >
            На главную
          </button>
        </div>
      </header>

      <main className="legal-page help-page shell">
        <section className="legal-intro help-intro">
          <div>
            <span className="section-kicker">Пошагово, с картинками</span>
            <h1>Как подключиться</h1>
            <p>
              Одна ссылка на все устройства. Выберите своё, и я проведу от
              установки приложения до первого подключения. Внизу раздел о
              том, что делать, если не заработало.
            </p>
          </div>
          <Mascot variant="phone" className="legal-mascot" decorative />
        </section>

        <nav className="help-tabs" aria-label="Выбор устройства">
          {PLATFORMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`help-tab${platform === item.id ? " help-tab-active" : ""}`}
              aria-pressed={platform === item.id}
              onClick={() => setPlatform(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <section className="help-guide" aria-live="polite">
          {platform === "ios" && <IosGuide />}
          {platform === "android" && <AndroidGuide />}
          {platform === "windows" && <WindowsGuide />}
          {platform === "router" && <RouterGuide />}
        </section>

        <section className="help-servers">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Что означают значки</span>
              <h2>Какой сервер выбрать</h2>
            </div>
          </div>
          <div className="help-legend">
            <div className="help-legend-item">
              <span className="help-legend-icon" aria-hidden="true">🌐</span>
              <div>
                <strong>Лучше с мобильного</strong>
                <p>Для интернета от оператора. В строгих сетях, офисных или гостиничных, может не проходить.</p>
              </div>
            </div>
            <div className="help-legend-item">
              <span className="help-legend-icon" aria-hidden="true">🛜</span>
              <div>
                <strong>Лучше с Wi-Fi и ПК</strong>
                <p>Идёт по стандартному порту 443. Проходит почти в любой сети, попробуйте его, если 🌐 молчит.</p>
              </div>
            </div>
          </div>
          <p className="help-note">
            Это подсказка, а не правило: оба варианта часто работают везде.
            Внутри каждой страны приложение само каждые три минуты проверяет
            все серверы и держит связь через самый быстрый. Если один упал,
            переключение произойдёт без Вашего участия.
          </p>
        </section>

        <Troubleshooting />

        <section className="legal-support-note help-support">
          <Mascot variant="support" className="help-mascot" decorative />
          <div>
            <h2>Не получилось</h2>
            <p>
              Напишите мне и скажите, какое у Вас устройство, какое приложение
              и что именно Вы видите. С этим я разберусь быстро, без этого буду
              переспрашивать.
            </p>
            <p>
              <a href={maxSupportUrl} target="_blank" rel="noreferrer">MAX</a>, работает
              без VPN ·{" "}
              <a href={`mailto:${supportEmail}`}>{supportEmail}</a> ·{" "}
              <a href={telegramSupportUrl} target="_blank" rel="noreferrer">Telegram</a>,
              нужен включённый VPN
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
