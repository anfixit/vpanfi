import { useState, type ReactNode } from "react";
import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import {
  maxSupportUrl,
  supportEmail,
  telegramBotUrl,
  telegramSupportUrl,
} from "../config";
import "../help.css";

/*
 * Страница для тех, кто подключается впервые и пришёл по ссылке друга.
 * В /help человек сначала выбирает устройство, потом раздел, потом шаг:
 * для новичка это три развилки до первого действия. Здесь один путь,
 * и единственная развилка та, без которой нельзя, какой App Store.
 *
 * 05.11.2026: incy убран отовсюду, его сняли с публикации в App Store.
 * Для айфона остался Happ: из зарубежного магазина напрямую, из
 * российского через TestFlight.
 */

type Store = "foreign" | "russian";

const APP_HAPP_IOS =
  "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215";
const APP_HAPP_TESTFLIGHT = "https://testflight.apple.com/join/ystvnbsP";
const APP_TESTFLIGHT = "https://apps.apple.com/app/testflight/id899247664";
const APP_V2RAGE = "https://apps.apple.com/us/app/v2rage/id6761075402";
const APP_RABBITHOLE =
  "https://apps.apple.com/ru/app/rabbithole-vpn-client/id6683309629";
const APP_HAPP_ANDROID =
  "https://play.google.com/store/apps/details?id=com.happproxy";
const APP_HAPP_APK =
  "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk";
const APP_HAPP_WINDOWS =
  "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe";

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

function InstallForeign() {
  return (
    <>
      <p>
        Приложение называется <strong>Happ</strong>. Само по себе оно ничего не
        включает: это пульт, который работает с Вашей подпиской. Платить внутри
        него не нужно.
      </p>
      <a
        className="button button-primary"
        href={APP_HAPP_IOS}
        target="_blank"
        rel="noreferrer"
      >
        Happ в App Store ↗
      </a>
      <p>
        Откройте магазин по кнопке и нажмите «Загрузить». Искать приложение по
        похожему названию не нужно.
      </p>
    </>
  );
}

function InstallRussian() {
  return (
    <>
      <p>
        Приложение называется <strong>Happ</strong>, и в российском App Store
        его нет. Ставим через <strong>TestFlight</strong>: это официальное
        приложение Apple, через него выдают программы, которых нет в магазине.
      </p>
      <ol className="help-cleanup-list">
        <li>
          Поставьте{" "}
          <a href={APP_TESTFLIGHT} target="_blank" rel="noreferrer">
            TestFlight
          </a>{" "}
          из App Store. Издатель Apple.
        </li>
        <li>Откройте нашу ссылку приглашения по кнопке ниже.</li>
        <li>
          Нажмите «Принять», затем «Установить». Happ появится на экране как
          обычное приложение.
        </li>
      </ol>
      <a
        className="button button-primary"
        href={APP_HAPP_TESTFLIGHT}
        target="_blank"
        rel="noreferrer"
      >
        Happ через TestFlight ↗
      </a>
      <Notice>
        <strong>Не ставьте «Happ» из российского App Store.</strong> Настоящего
        Happ там нет, а по этому запросу магазин показывает подделки: «Happ VPN
        ++», «Happ VPN Official», «Happ plus 2026» и похожие. С нашей подпиской
        они не работают.
      </Notice>
      <details className="help-detail">
        <summary>TestFlight не пустил: что делать</summary>
        <p>
          Бывает, что набор участников закрыт. Тогда подойдёт любое из этих
          приложений, они делают то же самое, разница только в названиях
          кнопок:
        </p>
        <p>
          <a href={APP_V2RAGE} target="_blank" rel="noreferrer">
            V2RAGE в App Store ↗
          </a>
          <br />
          <a href={APP_RABBITHOLE} target="_blank" rel="noreferrer">
            RabbitHole в App Store ↗
          </a>
        </p>
        <p>
          Если ни одно не ставится, напишите нам: подберём вариант под Ваш
          телефон.
        </p>
      </details>
    </>
  );
}

export function StartPage({
  theme,
  onToggleTheme,
  onOpenAuth,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
}) {
  const [store, setStore] = useState<Store>("foreign");

  return (
    <>
      <header className="site-header help-site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <a className="button button-ghost" href={routes.help}>
            Подробная помощь
          </a>
          <a className="button button-ghost" href={routes.landing}>
            На главную
          </a>
        </div>
      </header>
      <main className="help-page shell">
        <section className="help-intro">
          <div>
            <span className="section-kicker">
              Для тех, кто подключается впервые
            </span>
            <h1>
              Подключим за пять минут.
              <br />
              <span>Ничего настраивать не придётся.</span>
            </h1>
            <p>
              Нужны только телефон, интернет и пять минут. Платить на этом шаге
              не надо: первая неделя бесплатная, карту никто не спрашивает.
            </p>
          </div>
          <Mascot variant="phone" className="help-hero-mascot" decorative />
        </section>

        <section className="help-content-section">
          <div className="help-section-heading">
            <span className="section-kicker">Порядок такой</span>
            <h2>Три действия, остальное подсказки</h2>
            <p>
              Поставить приложение, взять подписку, вставить ссылку. Инструкция
              ниже написана для айфона. Для Android, Windows и Mac всё то же
              самое, меняется только приложение: это в самом низу страницы.
            </p>
          </div>
        </section>

        <nav className="help-tabs" aria-label="Какой у вас App Store">
          <button
            type="button"
            className={`help-tab${store === "foreign" ? " help-tab-active" : ""}`}
            aria-pressed={store === "foreign"}
            onClick={() => setStore("foreign")}
          >
            App Store не российский
          </button>
          <button
            type="button"
            className={`help-tab${store === "russian" ? " help-tab-active" : ""}`}
            aria-pressed={store === "russian"}
            onClick={() => setStore("russian")}
          >
            App Store российский
          </button>
        </nav>

        <details className="help-detail">
          <summary>Не знаю, какой у меня App Store</summary>
          <p>Проверить 20 секунд:</p>
          <ol className="help-cleanup-list">
            <li>Откройте «Настройки».</li>
            <li>Нажмите на своё имя в самом верху.</li>
            <li>
              «Медиаматериалы и покупки» → «Просмотреть». Может спросить пароль
              или Face ID.
            </li>
            <li>Строка «Страна и регион»: там и написано.</li>
          </ol>
          <p>
            США, Казахстан, Армения, Грузия и любая другая страна, кроме
            России, это левая кнопка «App Store не российский».
          </p>
        </details>

        <div className="help-layout">
          <div key={store} className="help-main-guide">
            <section
              className="help-content-section"
              aria-labelledby="start-steps-title"
            >
              <div className="help-section-heading">
                <h2 id="start-steps-title">Подключение по шагам</h2>
              </div>
              <ol className="help-steps">
                <Step n={1} title="Поставьте приложение">
                  {store === "foreign" ? <InstallForeign /> : <InstallRussian />}
                </Step>

                <Step n={2} title="Возьмите бесплатную неделю">
                  <p>
                    Семь дней, три устройства, без карты и без автосписаний.
                    Способа два, достаточно любого.
                  </p>
                  <button
                    className="button button-primary"
                    type="button"
                    onClick={onOpenAuth}
                  >
                    Получить неделю на сайте
                  </button>
                  <p>
                    Зарегистрируйтесь по почте, письмо со ссылкой придёт сразу.
                    Для сайта не нужен ни VPN, ни телеграм.
                  </p>
                  <p>
                    Или в телеграме:{" "}
                    <a href={telegramBotUrl} target="_blank" rel="noreferrer">
                      откройте нашего бота ↗
                    </a>
                    , нажмите «Старт» и возьмите пробный доступ.
                  </p>
                  <Notice>
                    <strong>Что должно прийти:</strong> ссылка подписки, длинная
                    строка, которая начинается с <code>https://</code>. Длинная
                    это нормально. Она и есть Ваш доступ, и вставлять в
                    приложение нужно именно её. Никому её не пересылайте: кто
                    получит ссылку, тот займёт место в Вашей подписке.
                  </Notice>
                </Step>

                <Step n={3} title="Вставьте ссылку в приложение">
                  <p>
                    <strong>Самый простой способ:</strong> нажмите на саму
                    ссылку там, где Вы её получили, в письме или в телеграме.
                    Телефон спросит, чем открыть, выберите Happ. Подписка
                    добавится сама.
                  </p>
                  <p>Если так не вышло, вручную:</p>
                  <ol className="help-cleanup-list">
                    <li>
                      Скопируйте ссылку целиком, от <code>https://</code> до
                      самого конца: удерживайте её и выберите «Скопировать
                      ссылку». Руками не набирайте.
                    </li>
                    <li>Откройте приложение.</li>
                    <li>Нажмите «+» в правом верхнем углу.</li>
                    <li>
                      Выберите «Вставить из буфера обмена». Пункт может
                      называться «Импорт из буфера обмена».
                    </li>
                  </ol>
                  <Notice>
                    <strong>Что должно получиться:</strong> на экране появилось
                    название VPaNfi и список серверов. Если список пустой или
                    приложение показывает ошибку, не переходите к следующему
                    шагу, а напишите нам.
                  </Notice>
                </Step>

                <Step n={4} title="Включите">
                  <ol className="help-cleanup-list">
                    <li>
                      Выберите самую верхнюю строку списка: «01 Автовыбор,
                      самый быстрый».
                    </li>
                    <li>Нажмите большую круглую кнопку подключения.</li>
                    <li>
                      Телефон попросит разрешить добавить конфигурацию VPN.
                      Проверьте, что в запросе указано имя Вашего приложения,
                      нажмите «Разрешить» и подтвердите кодом или Face ID. Это
                      спрашивают один раз, при первом подключении.
                    </li>
                  </ol>
                  <p>
                    Вверху экрана появится значок VPN. Выключается там же, где
                    включалось: та же кнопка в приложении.
                  </p>
                </Step>

                <Step n={5} title="Проверьте">
                  <p>
                    Откройте два разных сайта, а потом то, ради чего всё
                    затевалось. Значок VPN говорит только о том, что соединение
                    поднято, а настоящая проверка это загрузившаяся страница.
                  </p>
                </Step>
              </ol>
            </section>

            <section className="help-content-section">
              <div className="help-section-heading">
                <span className="section-kicker">Новое</span>
                <h2>Страну выбирать не надо</h2>
                <p>
                  Сверху списка стоят две строки автовыбора, они подойдут почти
                  всем.
                </p>
              </div>
              <ul className="help-cleanup-list">
                <li>
                  🌐 <strong>01 Автовыбор, самый быстрый</strong> когда Вы с
                  мобильного интернета
                </li>
                <li>
                  🛜 <strong>02 Автовыбор, самый быстрый</strong> когда Вы с
                  Wi-Fi или с компьютера
                </li>
              </ul>
              <p>
                Приложение само проверяет все серверы и подключается к тому,
                который отвечает быстрее всех именно с Вашего интернета. Если
                сервер пропадёт, оно так же само перейдёт на следующий, без
                Вашего участия.
              </p>
              <p>
                Выбор по странам никуда не делся. Нужен конкретно Казахстан или
                США, берите строку со страной. Значки там те же: 🌐 для
                мобильного интернета, 🛜 для Wi-Fi и компьютера. Не заработало с
                одним значком, попробуйте второй.
              </p>
            </section>

            <section className="help-content-section">
              <div className="help-section-heading">
                <span className="section-kicker">Если не получилось</span>
                <h2>Три вещи решают почти всё</h2>
              </div>
              <details className="help-detail">
                <summary>Проверьте, не включён ли другой VPN</summary>
                <p>
                  Наш туннель внутри чужого не поднимается, и это причина номер
                  один. Настройки → Основные → VPN и управление устройством →
                  VPN: удалите все конфигурации, кроме Вашего приложения. Там
                  же посмотрите профили.
                </p>
              </details>
              <details className="help-detail">
                <summary>Обновите подписку в приложении</summary>
                <p>
                  Круглая стрелка рядом с названием VPaNfi. Это первое
                  действие, если серверы перестали отвечать или в списке нет
                  строк автовыбора.
                </p>
              </details>
              <details className="help-detail">
                <summary>Попробуйте второй значок или другую страну</summary>
                <p>
                  В офисной, гостиничной и корпоративной сети обычно работает
                  только 🛜. Если в телеграме дрожит голос при звонках,
                  возьмите 🌐 той же страны: по нему голос идёт ровнее.
                </p>
              </details>
              <p>
                Не помогло? <a href={routes.help}>Подробный разбор поломок</a>{" "}
                или сразу напишите нам, разберёмся вместе.
              </p>
            </section>

            <section className="help-content-section">
              <div className="help-section-heading">
                <span className="section-kicker">Другие устройства</span>
                <h2>Не айфон</h2>
                <p>
                  Ссылка подписки одна и та же на всех устройствах, меняется
                  только приложение. Дальше всё так же: «+», «Вставить из
                  буфера обмена», верхняя строка автовыбора, подключиться.
                </p>
              </div>
              <ul className="help-cleanup-list">
                <li>
                  <strong>Android:</strong>{" "}
                  <a href={APP_HAPP_ANDROID} target="_blank" rel="noreferrer">
                    Happ в Google Play ↗
                  </a>
                  . Для телефонов без Google Play, например Huawei и Honor,{" "}
                  <a href={APP_HAPP_APK} target="_blank" rel="noreferrer">
                    файл APK ↗
                  </a>
                  .
                </li>
                <li>
                  <strong>Windows:</strong>{" "}
                  <a href={APP_HAPP_WINDOWS} target="_blank" rel="noreferrer">
                    установщик Happ для x64 ↗
                  </a>
                  . Для ARM-компьютера напишите нам.
                </li>
                <li>
                  <strong>Mac:</strong>{" "}
                  <a href={APP_HAPP_IOS} target="_blank" rel="noreferrer">
                    Happ в App Store ↗
                  </a>
                  .
                </li>
              </ul>
            </section>

            <section className="help-content-section">
              <div className="help-section-heading">
                <span className="section-kicker">Когда неделя кончится</span>
                <h2>Сколько это стоит</h2>
              </div>
              <p>
                Тарифы и оплата картой или через СБП на{" "}
                <a href={routes.buy}>странице покупки</a>. В любом тарифе три
                устройства: обычно это телефон, компьютер и кто-то из близких.
              </p>
              <p>
                Пока неделя идёт, ничего не спишется: карту мы на пробный
                период не спрашиваем.
              </p>
              <p>
                А если захотите рекомендовать сервис и продлить бесплатные дни,
                вот детали: <a href={routes.invite}>партнёрская программа</a>.
                Коротко: друг покупает по Вашей ссылке, и 15 дней приходят
                каждому из вас.
              </p>
            </section>
          </div>

          <aside className="help-contact">
            <Mascot variant="support" className="help-mascot" decorative />
            <span className="section-kicker">Можно сразу написать</span>
            <h2>Застряли? Помогу.</h2>
            <p>
              Не нужно разбираться самостоятельно. Напишите, на каком шаге
              остановились, и пришлите скриншот экрана. На скриншоте закройте
              ссылку подписки и QR-код.
            </p>
            <a
              className="button button-primary"
              href={telegramSupportUrl}
              target="_blank"
              rel="noreferrer"
            >
              Написать в Telegram ↗
            </a>
            <a
              className="button button-ghost"
              href={maxSupportUrl}
              target="_blank"
              rel="noreferrer"
            >
              Написать в MAX ↗
            </a>
            <a
              className="button button-ghost"
              href={`mailto:${supportEmail}?subject=${encodeURIComponent("Не получается подключить VPaNfi")}`}
            >
              Написать на почту
            </a>
            <p className="help-secondary">
              Почта и MAX открываются без VPN, телеграм не всегда. Пароли, коды
              из сообщений и номера карт поддержке не нужны никогда.
            </p>
          </aside>
        </div>

        <footer className="help-footer">
          <p>
            Названия пунктов могут отличаться в разных версиях системы и
            приложения. Если что-то не совпало с инструкцией, напишите нам:
            поправим страницу.
          </p>
          <p>
            Нужна инструкция для другого устройства или разбор поломки?{" "}
            <a href={routes.help}>Подробная помощь</a>.
          </p>
        </footer>
      </main>
    </>
  );
}
