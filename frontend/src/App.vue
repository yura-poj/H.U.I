<script setup>
import { computed, onMounted, ref } from "vue";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5001/api";

const username = ref("");
const password = ref("");
const token = ref(localStorage.getItem("hui_token") || "");
const user = ref(JSON.parse(localStorage.getItem("hui_user") || "null"));
const levels = ref([]);
const game = ref(null);
const insult = ref("");
const mode = ref("login");
const loading = ref(false);
const error = ref("");
const events = ref([]);

const isAuthed = computed(() => Boolean(token.value && user.value));
const currentLevel = computed(() => {
  if (!game.value) {
    return levels.value.find((level) => level.id === user.value?.current_level_id);
  }

  return levels.value.find((level) => level.id === game.value.level_id);
});
const hpPercent = computed(() => {
  if (!game.value) {
    return 0;
  }

  return Math.max(0, Math.round((game.value.monster.hp / game.value.monster.max_hp) * 100));
});

function rememberSession(nextToken, nextUser) {
  token.value = nextToken;
  user.value = nextUser;
  localStorage.setItem("hui_token", nextToken);
  localStorage.setItem("hui_user", JSON.stringify(nextUser));
}

function clearSession() {
  token.value = "";
  user.value = null;
  game.value = null;
  events.value = [];
  localStorage.removeItem("hui_token");
  localStorage.removeItem("hui_user");
}

function pushEvent(entry) {
  events.value = [entry, ...events.value].slice(0, 8);
}

async function request(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token.value ? { Authorization: `Bearer ${token.value}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || `request_failed_${response.status}`);
  }

  return data;
}

async function loadLevels() {
  const data = await request("/levels");
  levels.value = data.levels;
}

async function submitAuth() {
  error.value = "";
  loading.value = true;

  try {
    const path = mode.value === "register" ? "/users/register" : "/users/login";
    const data = await request(path, {
      method: "POST",
      body: JSON.stringify({ username: username.value, password: password.value }),
    });

    rememberSession(data.token, data.user);
    await loadLevels();
    await startGame();
  } catch (err) {
    error.value = humanError(err.message);
  } finally {
    loading.value = false;
  }
}

async function startGame() {
  error.value = "";
  loading.value = true;

  try {
    const data = await request("/games", { method: "POST" });
    game.value = data.game;
    pushEvent({
      type: "system",
      text: `New fight: ${data.game.monster.name}`,
      damage: null,
    });
  } catch (err) {
    error.value = humanError(err.message);
  } finally {
    loading.value = false;
  }
}

async function submitInsult() {
  if (!game.value || !insult.value.trim()) {
    return;
  }

  error.value = "";
  loading.value = true;
  const text = insult.value.trim();

  try {
    const data = await request(`/games/${game.value.id}/insults`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });

    game.value = data.game;
    insult.value = "";
    pushEvent({
      type: data.accepted ? "hit" : "blocked",
      text,
      damage: data.damage,
      reason: data.reason,
      reply: data.monster_reply,
      advancedTo: data.advanced_to_level_id,
    });

    if (data.advanced_to_level_id) {
      user.value = { ...user.value, current_level_id: data.advanced_to_level_id };
      localStorage.setItem("hui_user", JSON.stringify(user.value));
    }
  } catch (err) {
    error.value = humanError(err.message);
  } finally {
    loading.value = false;
  }
}

function humanError(code) {
  const messages = {
    invalid_credentials: "Wrong username or password.",
    username_taken: "This username is already taken.",
    username_too_short: "Username must be at least 3 characters.",
    password_too_short: "Password must be at least 6 characters.",
    authentication_required: "Log in to continue.",
    invalid_token: "Session expired. Log in again.",
    game_not_found: "Game was not found.",
    game_already_finished: "This monster is already defeated.",
  };

  return messages[code] || code;
}

onMounted(async () => {
  if (!isAuthed.value) {
    return;
  }

  try {
    await loadLevels();
  } catch (err) {
    error.value = humanError(err.message);
  }
});
</script>

<template>
  <main class="app-shell">
    <section class="stage">
      <div class="topbar">
        <div>
          <p class="eyebrow">Monster insult arena</p>
          <h1>Break the monster with words</h1>
        </div>
        <button v-if="isAuthed" class="ghost-button" type="button" @click="clearSession">Log out</button>
      </div>

      <div v-if="!isAuthed" class="auth-layout">
        <form class="auth-panel" @submit.prevent="submitAuth">
          <div class="tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              :class="{ active: mode === 'login' }"
              @click="mode = 'login'"
            >
              Login
            </button>
            <button
              type="button"
              :class="{ active: mode === 'register' }"
              @click="mode = 'register'"
            >
              Register
            </button>
          </div>

          <label>
            Username
            <input v-model="username" autocomplete="username" name="username" required />
          </label>
          <label>
            Password
            <input
              v-model="password"
              autocomplete="current-password"
              name="password"
              required
              type="password"
            />
          </label>

          <p v-if="error" class="error">{{ error }}</p>
          <button class="primary-button" :disabled="loading" type="submit">
            {{ loading ? "Working..." : mode === "register" ? "Create player" : "Enter arena" }}
          </button>
        </form>
      </div>

      <div v-else class="game-layout">
        <aside class="side-panel">
          <div class="player-block">
            <span class="avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
            <div>
              <p class="label">Player</p>
              <strong>{{ user.username }}</strong>
            </div>
          </div>

          <div class="level-list">
            <p class="label">Level path</p>
            <div
              v-for="level in levels"
              :key="level.id"
              class="level-row"
              :class="{ current: level.id === user.current_level_id }"
            >
              <span>{{ level.order }}</span>
              <div>
                <strong>{{ level.title }}</strong>
                <small>{{ level.monster.name }}</small>
              </div>
            </div>
          </div>
        </aside>

        <section class="fight">
          <div v-if="!game" class="empty-fight">
            <button class="primary-button" :disabled="loading" type="button" @click="startGame">
              Start current level
            </button>
          </div>

          <template v-else>
            <div class="monster-panel">
              <div class="monster-art">
                <img :src="game.monster.icon" :alt="game.monster.name" />
              </div>
              <div class="monster-info">
                <p class="label">Current monster</p>
                <h2>{{ game.monster.name }}</h2>
                <p>{{ currentLevel?.description }}</p>
                <div class="hp-row">
                  <span>HP</span>
                  <strong>{{ game.monster.hp }} / {{ game.monster.max_hp }}</strong>
                </div>
                <div class="hp-bar" aria-label="Monster HP">
                  <span :style="{ width: `${hpPercent}%` }"></span>
                </div>
              </div>
            </div>

            <form class="insult-form" @submit.prevent="submitInsult">
              <label>
                Insult
                <textarea
                  v-model="insult"
                  :disabled="game.status !== 'active'"
                  :placeholder="`At least ${game.rules.min_words_per_insult} words`"
                  rows="4"
                ></textarea>
              </label>
              <div class="action-row">
                <p v-if="error" class="error">{{ error }}</p>
                <button
                  class="primary-button"
                  :disabled="loading || game.status !== 'active' || !insult.trim()"
                  type="submit"
                >
                  Hit with words
                </button>
              </div>
            </form>

            <div v-if="game.status === 'won'" class="victory-band">
              <strong>Monster defeated.</strong>
              <button class="ghost-button" type="button" @click="startGame">Next fight</button>
            </div>
          </template>
        </section>

        <aside class="history-panel">
          <p class="label">Recent attempts</p>
          <div v-if="events.length === 0" class="empty-history">No insults yet.</div>
          <article v-for="event in events" :key="`${event.text}-${event.reply}`" class="event-card">
            <div class="event-top">
              <span :class="['status-dot', event.type]"></span>
              <strong>{{ event.type === "hit" ? `${event.damage} damage` : event.type }}</strong>
            </div>
            <p v-if="event.text" class="event-text">{{ event.text }}</p>
            <small v-if="event.reply">{{ event.reply }}</small>
            <small v-if="event.reason === 'duplicate_insult'">Already used by this player.</small>
            <small v-if="event.reason === 'min_words'">Too short for this level.</small>
            <small v-if="event.advancedTo">Advanced to {{ event.advancedTo }}.</small>
          </article>
        </aside>
      </div>
    </section>
  </main>
</template>
