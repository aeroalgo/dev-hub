window.__ModuleLoader__.load({
  id: '@dev-hub/dsh-mb-bridge',
  factory: () => {
    const module = { exports: {} };
    const exports = module.exports;

    const WORKSPACE_FILTER_KEY = 'mb-bridge.workspaceFilter';
    const inject = [];

    function readWorkspaceFilter() {
      try {
        return localStorage.getItem(WORKSPACE_FILTER_KEY) ?? '';
      } catch {
        return '';
      }
    }

    function saveWorkspaceFilter(value) {
      try {
        localStorage.setItem(WORKSPACE_FILTER_KEY, value);
      } catch {
        /* ignore */
      }
    }

    async function callBridge(action, taskId, extra = {}) {
      const response = await fetch('/api/mb-bridge/action', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          requestId: crypto.randomUUID(),
          action: { action, taskId, ...extra },
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || payload.stderr || 'mb-bridge action failed');
      }
      return payload;
    }

    function syncSummary(payload) {
      const text = `${payload.stdout || ''}\n${payload.stderr || ''}`;
      const matches = text.match(/(?:upsert|archive|noop)=\d+/g);
      return matches ? matches.join(' ') : (payload.ok ? 'sync complete' : 'sync failed');
    }

    function appendWorkspaceOptions(workspaceSelect, items) {
      const seen = new Set(['']);
      for (const option of workspaceSelect.options) {
        seen.add(option.value);
      }
      for (const item of items) {
        if (!item || typeof item.id !== 'string' || item.id === '' || seen.has(item.id)) continue;
        seen.add(item.id);
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = typeof item.label === 'string' && item.label !== '' ? item.label : item.id.slice(0, 8);
        workspaceSelect.appendChild(option);
      }
    }

    async function loadWorkspaceOptions(workspaceSelect) {
      const response = await fetch('/api/mb-bridge/workspaces');
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || 'workspace list failed');
      }
      appendWorkspaceOptions(workspaceSelect, Array.isArray(payload.items) ? payload.items : []);
    }

    function mountControls(root) {
      if (!root || root.querySelector('[data-mb-bridge-controls="true"]')) return;

      const bar = document.createElement('div');
      bar.dataset.mbBridgeControls = 'true';
      bar.style.display = 'flex';
      bar.style.gap = '8px';
      bar.style.alignItems = 'center';
      bar.style.flexWrap = 'wrap';
      bar.style.margin = '8px 0';

      const workspaceLabel = document.createElement('label');
      workspaceLabel.textContent = 'Workspace ';
      const workspaceSelect = document.createElement('select');
      workspaceSelect.innerHTML = '<option value="">All</option>';
      workspaceLabel.appendChild(workspaceSelect);

      const status = document.createElement('span');
      status.style.opacity = '0.8';

      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Sync memory-bank';

      const refreshLabel = () => {
        const selected = workspaceSelect.value;
        button.textContent = selected ? 'Sync workspace' : 'Sync all workspaces';
      };

      workspaceSelect.addEventListener('change', () => {
        saveWorkspaceFilter(workspaceSelect.value);
        refreshLabel();
      });

      button.addEventListener('click', async () => {
        button.disabled = true;
        status.textContent = 'Syncing…';
        try {
          const workspaceId = workspaceSelect.value || undefined;
          const payload = await callBridge('sync', 'board', workspaceId ? { workspaceId } : {});
          status.textContent = syncSummary(payload);
          window.dispatchEvent(new CustomEvent('mb-bridge-sync-complete'));
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : 'sync failed';
        } finally {
          button.disabled = false;
        }
      });

      bar.appendChild(workspaceLabel);
      bar.appendChild(button);
      bar.appendChild(status);
      root.prepend(bar);

      loadWorkspaceOptions(workspaceSelect)
        .then(() => {
          const saved = readWorkspaceFilter();
          if (saved && [...workspaceSelect.options].some((option) => option.value === saved)) {
            workspaceSelect.value = saved;
          } else if (workspaceSelect.options.length === 2) {
            workspaceSelect.value = workspaceSelect.options[1].value;
            saveWorkspaceFilter(workspaceSelect.value);
          }
          refreshLabel();
        })
        .catch((error) => {
          status.textContent = error instanceof Error ? error.message : 'workspace list unavailable';
        });

      fetch('/api/task-board/state')
        .then((response) => response.json())
        .then((snapshot) => {
          const tasks = Array.isArray(snapshot.tasks) ? snapshot.tasks : [];
          const fromTasks = [];
          const seen = new Set();
          for (const task of tasks) {
            const id = task && task.workspace_id;
            if (typeof id !== 'string' || id === '' || seen.has(id)) continue;
            seen.add(id);
            fromTasks.push({ id, label: id.slice(0, 8) });
          }
          appendWorkspaceOptions(workspaceSelect, fromTasks);
          const saved = readWorkspaceFilter();
          if (saved && [...workspaceSelect.options].some((option) => option.value === saved)) {
            workspaceSelect.value = saved;
          }
          refreshLabel();
        })
        .catch(() => {
          /* optional enrichment */
        });
    }

    function ensureMounted() {
      const board = document.querySelector('[data-dsh-taskboard-board]');
      if (!board) return;
      const header = board.querySelector('header') ?? board;
      mountControls(header);
    }

    let disposeObserver;

    function apply() {
      ensureMounted();
      if (disposeObserver) return;
      const observer = new MutationObserver(() => ensureMounted());
      observer.observe(document.documentElement, { childList: true, subtree: true });
      disposeObserver = () => observer.disconnect();
    }

    exports.inject = inject;
    exports.apply = apply;
    return module.exports;
  },
});
