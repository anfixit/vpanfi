import { navigate, routes } from "../app/navigation";
import { Mascot } from "../components/Mascot";

export function NotFoundPage() {
  return (
    <main className="not-found shell">
      <Mascot variant="error" className="not-found-mascot" decorative />
      <span className="section-kicker">Ошибка 404</span>
      <h1>Кажется, мы свернули не на ту лиану</h1>
      <p className="muted">Такой страницы нет или она была перемещена.</p>
      <button className="button button-primary button-large" type="button" onClick={() => navigate(routes.landing)}>Вернуться на главную</button>
    </main>
  );
}
