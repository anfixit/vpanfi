import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { InviteCard } from "../components/InviteCard";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { telegramSupportUrl } from "../config";
import { inviterFromUrl } from "../referral";
import "../help.css";

/*
 * Партнёрская программа на отдельной странице: её адрес можно дать
 * словами и вставить в рассылку, а раньше условия жили только в боте
 * и в карточке на странице «куда написать».
 *
 * Если страницу открыли из приложения (в адресе есть ?u=имя учётки),
 * сверху сразу показывается готовая личная ссылка: человек пришёл за
 * ней, а не за условиями.
 */

export function InvitePage({
  theme,
  onToggleTheme,
}: {
  theme: Theme;
  onToggleTheme: () => void;
}) {
  const inviter = inviterFromUrl();

  return (
    <>
      <header className="site-header help-site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <a className="button button-ghost" href={routes.help}>
            Инструкции
          </a>
          <a className="button button-ghost" href={routes.landing}>
            На главную
          </a>
        </div>
      </header>
      <main className="help-page shell">
        <section className="help-intro">
          <div>
            <span className="section-kicker">Партнёрская программа</span>
            <h1>
              Приведите друга.
              <br />
              <span>Бесплатные дни получите оба.</span>
            </h1>
            <p>
              Если Вам нравится VPaNfi и Вы готовы его рекомендовать, за это
              будут дни подписки. И Вам, и другу.
            </p>
          </div>
          <Mascot variant="greeting" className="help-hero-mascot" decorative />
        </section>

        {inviter && <InviteCard username={inviter} />}

        <section className="help-content-section">
          <div className="help-section-heading">
            <span className="section-kicker">Условия</span>
            <h2>Месяц за одного друга</h2>
          </div>
          <ol className="help-cleanup-list">
            <li>
              <strong>15 дней другу</strong> к его первой покупке по Вашей
              ссылке.
            </li>
            <li>
              <strong>15 дней Вам</strong>, как только друг оплатил.
            </li>
            <li>
              <strong>Ещё 15 дней Вам</strong>, когда друг первый раз продлит
              подписку.
            </li>
          </ol>
          <p>
            Получается месяц подписки за одного друга, который остался с нами.
            Друзей можно приводить сколько угодно, ограничений нет.
          </p>
          <div className="help-note">
            Дни приходят сами: за покупку на сайте за несколько минут, за
            покупку в телеграм-боте в течение часа. Просить их не нужно.
          </div>
        </section>

        <section className="help-content-section">
          <div className="help-section-heading">
            <span className="section-kicker">Шаг первый</span>
            <h2>Где взять свою ссылку</h2>
            <p>Три способа, выбирайте любой.</p>
          </div>
          <ol className="help-cleanup-list">
            <li>
              <strong>В приложении.</strong> Работает и у тех, кто покупал в
              боте, и у тех, кто на сайте. Нажмите круглую стрелку обновления
              рядом с названием VPaNfi, затем кнопку поддержки: она в блоке
              VPaNfi справа, в одной строке с полоской гигабайтов. Откроется
              страница, на ней «🎁 Ваша ссылка приглашения», дальше
              «Поделиться» или «Скопировать ссылку».
            </li>
            <li>
              <strong>В личном кабинете</strong>, если покупали на сайте:{" "}
              <a href={routes.dashboard}>откройте кабинет</a>, на главной будет
              карточка «Пригласите друга».
            </li>
            <li>
              <strong>Попросить у поддержки.</strong> Напишите{" "}
              <a href={telegramSupportUrl} target="_blank" rel="noreferrer">
                Артёму ↗
              </a>{" "}
              «хочу пригласить друга», и он пришлёт ссылку сообщением.
            </li>
          </ol>
        </section>

        <section className="help-content-section">
          <div className="help-section-heading">
            <span className="section-kicker">Шаг второй</span>
            <h2>Что делает друг</h2>
          </div>
          <p>
            Открывает Вашу ссылку и покупает так, как ему удобно: сразу на
            сайте или по кнопке «Купить в Telegram». Для покупки на сайте не
            нужен ни VPN, ни телеграм.
          </p>
          <div className="help-note">
            <strong>Важно:</strong> друг должен зайти именно по Вашей ссылке.
            Если он откроет сайт или бота сам, мы не увидим, кто его привёл, и
            дни не придут никому.
          </div>
          <p>
            Другу, который подключается впервые, пригодится{" "}
            <a href={routes.start}>инструкция по шагам</a>: там всё от установки
            приложения до первого подключения.
          </p>
        </section>

        <footer className="help-footer">
          <p>
            Вопрос по дням или по ссылке?{" "}
            <a href={telegramSupportUrl} target="_blank" rel="noreferrer">
              Напишите в поддержку
            </a>
            , разберёмся.
          </p>
        </footer>
      </main>
    </>
  );
}
