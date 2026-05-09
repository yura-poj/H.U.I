import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const PLAYER = {
  id: "user-1",
  username: "player",
  current_level_id: "level_1",
  current_monster_hp: 20,
};

const LEVELS = [
  {
    id: "level_1",
    title: "Level 1",
    description: "Requires at least 3 words.",
    monster: {
      name: "Monster 1",
      icon: "/1.png",
      icon_file: "1.png",
    },
    rules: {
      hp: 20,
      min_words_per_insult: 3,
    },
  },
];

function game(overrides = {}) {
  const { monster = {}, rules = {}, ...rest } = overrides;

  return {
    id: "game-1",
    level_id: "level_1",
    status: "active",
    monster: {
      name: "Monster 1",
      icon: "/1.png",
      icon_file: "1.png",
      hp: 20,
      max_hp: 20,
      ...monster,
    },
    rules: {
      min_words_per_insult: 3,
      ...rules,
    },
    ...rest,
  };
}

function response(data, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });
}

function rememberPlayer() {
  localStorage.setItem("hui_token", "token-1");
  localStorage.setItem("hui_user", JSON.stringify(PLAYER));
}

function createStorage() {
  const values = new Map();

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    setItem: vi.fn((key, value) => values.set(key, String(value))),
    removeItem: vi.fn((key) => values.delete(key)),
    clear: vi.fn(() => values.clear()),
  };
}

function installStorage() {
  const storage = createStorage();

  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: storage,
  });
  vi.stubGlobal("localStorage", storage);
}

async function loadApp(apiUrl) {
  vi.resetModules();
  import.meta.env.VITE_API_URL = apiUrl || "http://localhost:5001/api";
  return (await import("./App.vue")).default;
}

function createFetch(overrides = {}) {
  return vi.fn((url, options = {}) => {
    const method = options.method || "GET";
    const { pathname } = new URL(String(url));
    const key = `${method} ${pathname}`;

    if (overrides[key]) {
      return overrides[key](url, options);
    }

    if (key === "GET /api/levels") {
      return response({ levels: LEVELS });
    }

    if (key === "POST /api/games") {
      return response({ game: game() }, 201);
    }

    if (key === "GET /api/insults/history") {
      return response({ history: [] });
    }

    if (key === "GET /api/leaderboard") {
      return response({ leaders: [], current_user_rank: null });
    }

    throw new Error(`Unhandled request: ${key}`);
  });
}

async function mountAuthed({ apiUrl, fetchMock = createFetch() } = {}) {
  rememberPlayer();
  vi.stubGlobal("fetch", fetchMock);

  const App = await loadApp(apiUrl);
  const wrapper = mount(App);

  for (let attempt = 0; attempt < 10 && !wrapper.find("textarea").exists(); attempt += 1) {
    await flushPromises();
  }

  return { wrapper, fetchMock };
}

beforeEach(() => {
  installStorage();
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App API contract behavior", () => {
  it("shows a retry action when an authenticated fight cannot load", async () => {
    rememberPlayer();
    const fetchMock = vi.fn(() => response({
      error: "rate_limit_exceeded",
      retry_after_seconds: 12,
    }, 429));
    vi.stubGlobal("fetch", fetchMock);

    const App = await loadApp();
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.text()).toContain("Слишком много запросов. Повторите через 12 секунд.");
    expect(wrapper.text()).toContain("Повторить");
    expect(wrapper.text()).not.toBe("Готовим бой...");

    await wrapper.find("button.retry-fight").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("maps registration IP limit errors with the daily limit", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({
      error: "registration_ip_limit_exceeded",
      limit: 3,
    }, 429)));

    const App = await loadApp();
    const wrapper = mount(App);

    await wrapper.findAll(".tabs button")[1].trigger("click");
    await wrapper.find("input[name='username']").setValue("new-player");
    await wrapper.find("input[name='password']").setValue("secret123");
    await wrapper.find("form.auth-panel").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("С этого адреса уже создано 3 игрока за сутки. Попробуйте завтра.");
  });

  it("maps rate limit errors with retry-after seconds", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({
      error: "rate_limit_exceeded",
      retry_after_seconds: 7,
    }, 429)));

    const App = await loadApp();
    const wrapper = mount(App);

    await wrapper.find("input[name='username']").setValue("player");
    await wrapper.find("input[name='password']").setValue("secret123");
    await wrapper.find("form.auth-panel").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Слишком много запросов. Повторите через 7 секунд.");
  });

  it("shows username and lets the authenticated player log out", async () => {
    const { wrapper } = await mountAuthed();

    expect(wrapper.text()).toContain("player");

    await wrapper.find("button.logout-button").trigger("click");

    expect(localStorage.getItem("hui_token")).toBeNull();
    expect(localStorage.getItem("hui_user")).toBeNull();
    expect(wrapper.text()).toContain("Войти на арену");
  });

  it("does not render a hit result or -0 animation for accepted zero damage", async () => {
    const fetchMock = createFetch({
      "POST /api/games/game-1/insults": () => response({
        accepted: true,
        damage: 0,
        score: {
          source: "model",
          toxic: false,
          toxicity_score: 0.1,
          label: "normal",
          signals: {},
        },
        monster_reply: "Фраза прозвучала, но монстр только моргнул.",
        game: game(),
      }),
    });
    const { wrapper } = await mountAuthed({ fetchMock });

    await wrapper.find("textarea").setValue("смешной пустой хлопок");
    await wrapper.find("form.insult-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Фраза засчитана, но не сработала");
    expect(wrapper.text()).toContain("0 урона");
    expect(wrapper.text()).not.toContain("Попадание на 0/10");
    expect(wrapper.text()).not.toContain("-0");
  });

  it("marks auth tabs and monster HP with accessible roles and values", async () => {
    const App = await loadApp();
    const authWrapper = mount(App);
    const tabs = authWrapper.findAll("[role='tab']");

    expect(tabs).toHaveLength(2);
    expect(tabs[0].attributes("aria-selected")).toBe("true");
    expect(tabs[1].attributes("aria-selected")).toBe("false");

    const { wrapper } = await mountAuthed();
    const hp = wrapper.find("[role='progressbar'][aria-label='Жизни монстра']");

    expect(hp.exists()).toBe(true);
    expect(hp.attributes("aria-valuemin")).toBe("0");
    expect(hp.attributes("aria-valuemax")).toBe("20");
    expect(hp.attributes("aria-valuenow")).toBe("20");
  });

  it("clears session and returns to login view on invalid_token 401", async () => {
    rememberPlayer();
    vi.stubGlobal("fetch", vi.fn(() => response({ error: "invalid_token" }, 401)));

    const App = await loadApp();
    const wrapper = mount(App);
    await flushPromises();

    expect(localStorage.getItem("hui_token")).toBeNull();
    expect(localStorage.getItem("hui_user")).toBeNull();
    expect(wrapper.text()).toContain("Сессия истекла. Войдите снова.");
    expect(wrapper.text()).toContain("Войти на арену");
  });

  it("clears session and returns to login view on authentication_required 401", async () => {
    rememberPlayer();
    vi.stubGlobal("fetch", vi.fn(() => response({ error: "authentication_required" }, 401)));

    const App = await loadApp();
    const wrapper = mount(App);
    await flushPromises();

    expect(localStorage.getItem("hui_token")).toBeNull();
    expect(wrapper.text()).toContain("Войдите, чтобы продолжить.");
    expect(wrapper.text()).toContain("Вход");
  });

  it("renders duplicate and min_words rejected attempts in combat log", async () => {
    let attempts = 0;
    const fetchMock = createFetch({
      "POST /api/games/game-1/insults": () => {
        attempts += 1;

        if (attempts === 1) {
          return response({
            accepted: false,
            reason: "duplicate_insult",
            damage: 0,
            monster_reply: "The monster has already heard that one.",
            game: game(),
          });
        }

        return response({
          accepted: false,
          reason: "min_words",
          required_words: 3,
          actual_words: 1,
          damage: 0,
          monster_reply: "The monster waits for a sharper insult.",
          game: game(),
        });
      },
    });
    const { wrapper } = await mountAuthed({ fetchMock });

    await wrapper.find("textarea").setValue("старый смешной бублик");
    await wrapper.find("form.insult-form").trigger("submit");
    await flushPromises();
    await wrapper.find("textarea").setValue("коротко");
    await wrapper.find("form.insult-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Повтор не засчитан");
    expect(wrapper.text()).toContain("Жизни монстра не изменились");
    expect(wrapper.text()).toContain("Нужно больше слов");
    expect(wrapper.text()).toContain("слишком короткое");
  });

  it("uses 409 game payload to refresh fight state and show stale session event", async () => {
    const fetchMock = createFetch({
      "POST /api/games/game-1/insults": () => response({
        accepted: false,
        reason: "stale_game_session",
        damage: 0,
        error: "stale_game_session",
        game: game({
          id: "game-2",
          monster: {
            hp: 12,
          },
        }),
      }, 409),
    });
    const { wrapper } = await mountAuthed({ fetchMock });

    await wrapper.find("textarea").setValue("устаревший смешной удар");
    await wrapper.find("form.insult-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Жизни 12 / 20");
    expect(wrapper.text()).toContain("Бой устарел");
    expect(wrapper.text()).toContain("Сохранен другой текущий бой");
  });

  it("normalizes trailing slash in VITE_API_URL", async () => {
    const { fetchMock } = await mountAuthed({
      apiUrl: "http://example.test/api/",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("http://example.test/api/levels");
  });

  it("shows word counter and keeps submit disabled until text is present", async () => {
    const { wrapper } = await mountAuthed();
    const submit = wrapper.find("form.insult-form button[type='submit']");

    expect(wrapper.text()).toContain("0 / 3 слов");
    expect(submit.attributes("disabled")).toBeDefined();

    await wrapper.find("textarea").setValue("один два три");

    expect(wrapper.text()).toContain("3 / 3 слов");
    expect(submit.attributes("disabled")).toBeUndefined();
  });

  it("submits the insult when Enter is pressed in the textarea", async () => {
    const fetchMock = createFetch({
      "POST /api/games/game-1/insults": () => response({
        accepted: true,
        damage: 4,
        score: {
          source: "model",
          toxic: false,
          toxicity_score: 0.1,
          label: "normal",
          signals: {},
        },
        monster_reply: "Монстр поперхнулся.",
        game: game({
          monster: {
            hp: 16,
          },
        }),
      }),
    });
    const { wrapper } = await mountAuthed({ fetchMock });
    const textarea = wrapper.find("textarea");

    await textarea.setValue("один два три");
    await textarea.trigger("keydown", { key: "Enter" });
    await flushPromises();

    const insultRequest = fetchMock.mock.calls.find(([url, options = {}]) => (
      String(url).endsWith("/api/games/game-1/insults") && options.method === "POST"
    ));

    expect(insultRequest).toBeDefined();
    expect(JSON.parse(insultRequest[1].body)).toEqual({ text: "один два три" });
    expect(wrapper.text()).toContain("Попадание на 4/10");
  });
});
