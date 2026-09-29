import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Folder,
  FolderSearch,
  HardDrive,
  Loader,
  Lock,
  Plus,
  Send,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import type { SseProgress } from "../../../../services/httpClient";
import { sseOverallPercent } from "../../../../services/httpClient";
import { playSound } from "../../../../lib/sound";

import {
  browseFilmiumFilesystem,
  getFilmiumDisks,
  getFilmiumMediaFileTree,
  transferFilmiumMediaStream,
  type FilmiumBrowse,
  type FilmiumDisk,
  type FilmiumFileTreeItem,
} from "../../../../services/filmiumMediaSourceApi";
import {
  addToFilmiumShareQueue,
  createFilmiumShareProfile,
  listFilmiumShareProfiles,
  type FilmiumShareProfile,
} from "../../../../services/filmiumShareApi";

const LAST_PROFILE_KEY = "filmium:last-share-profile";
const RECENT_KEY = "filmium:transfer-recent";

// Grupisanje fajlova u sklopive foldere u stablu za prenos.
const GROUP_ORDER = ["video", "subtitle", "image", "other"] as const;
const GROUP_LABEL: Record<string, string> = {
  video: "Video",
  subtitle: "Prevodi",
  image: "Slike",
  other: "Ostalo",
};


// ==========          SVOJSTVA PANELA          ==========

type FilmiumTransferPanelProps = {
  mediaId: number;
  title: string;
  onClose: () => void;
};


/**
 * Čitljiva veličina iz bajtova.
 */
function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const rounded =
    value >= 100 || unit === 0 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${units[unit]}`;
}


/**
 * „Prebaci" panel: levo stablo fajlova (štikliranje), desno izbor diska i
 * odredišnog foldera; kopira izabrane fajlove (original ostaje).
 */
function FilmiumTransferPanel({
  mediaId,
  title,
  onClose,
}: FilmiumTransferPanelProps) {
  const [files, setFiles] = useState<FilmiumFileTreeItem[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [openGroups, setOpenGroups] =
    useState<Record<string, boolean>>({});
  const [disks, setDisks] = useState<FilmiumDisk[]>([]);
  const [browse, setBrowse] = useState<FilmiumBrowse | null>(null);
  const [destination, setDestination] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>(() => {
    try {
      const raw = window.localStorage.getItem(RECENT_KEY);
      const parsed = raw ? (JSON.parse(raw) as unknown) : [];
      return Array.isArray(parsed)
        ? parsed.filter((entry): entry is string => typeof entry === "string")
        : [];
    } catch {
      return [];
    }
  });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<SseProgress | null>(null);
  const [done, setDone] = useState(false);
  const dirInputRef = useRef<HTMLInputElement>(null);

  // Native folder picker (webkitdirectory nije u React tipovima).
  useEffect(() => {
    dirInputRef.current?.setAttribute("webkitdirectory", "");
    dirInputRef.current?.setAttribute("directory", "");
  }, []);

  function rememberLocation(path: string): void {
    setRecent((prev) => {
      const next = [path, ...prev.filter((entry) => entry !== path)].slice(
        0,
        8,
      );
      try {
        window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  function lockDestination(path: string): void {
    setDestination(path);
    rememberLocation(path);
    setDone(false);
  }
  const [profiles, setProfiles] = useState<FilmiumShareProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] =
    useState<number | null>(null);
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileDest, setNewProfileDest] = useState("VIDEOS");

  // Profili: učitaj i auto-selektuj poslednje korišćen (ili prvi).
  useEffect(() => {
    let active = true;
    listFilmiumShareProfiles()
      .then((list) => {
        if (!active) {
          return;
        }
        setProfiles(list);
        const last = Number(
          window.localStorage.getItem(LAST_PROFILE_KEY),
        );
        const preferred =
          list.find((profile) => profile.id === last) ?? list[0];
        setSelectedProfileId(preferred?.id ?? null);
      })
      .catch(() => {
        /* tolerantno */
      });
    return () => {
      active = false;
    };
  }, []);

  // ESC zatvara.
  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Učitaj fajlove (default svi štiklirani), diskove i korene foldera.
  useEffect(() => {
    let active = true;
    getFilmiumMediaFileTree(mediaId)
      .then((tree) => {
        if (active) {
          setFiles(tree);
          setChecked(new Set(tree.map((file) => file.relative_path)));
        }
      })
      .catch(() => {
        /* tolerantno */
      });
    getFilmiumDisks()
      .then((list) => active && setDisks(list))
      .catch(() => {});
    browseFilmiumFilesystem()
      .then((data) => active && setBrowse(data))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [mediaId]);

  const allChecked = files.length > 0 && checked.size === files.length;

  function toggleFile(path: string): void {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  function toggleAll(): void {
    setChecked(
      allChecked ? new Set() : new Set(files.map((file) => file.relative_path)),
    );
  }

  // Grupisani fajlovi po tipu (Video / Prevodi / Slike / Ostalo).
  const groupedFiles = useMemo(() => {
    const map = new Map<string, FilmiumFileTreeItem[]>();
    for (const file of files) {
      const role = GROUP_LABEL[file.role] ? file.role : "other";
      const bucket = map.get(role) ?? [];
      bucket.push(file);
      map.set(role, bucket);
    }
    return map;
  }, [files]);

  function isGroupOpen(role: string): boolean {
    return openGroups[role] ?? true;
  }

  function toggleGroup(role: string): void {
    setOpenGroups((prev) => ({ ...prev, [role]: !(prev[role] ?? true) }));
  }

  function toggleGroupFiles(groupFiles: FilmiumFileTreeItem[]): void {
    setChecked((prev) => {
      const next = new Set(prev);
      const allOn = groupFiles.every((file) =>
        next.has(file.relative_path),
      );
      for (const file of groupFiles) {
        if (allOn) {
          next.delete(file.relative_path);
        } else {
          next.add(file.relative_path);
        }
      }
      return next;
    });
  }

  function openFolder(path: string | undefined): void {
    browseFilmiumFilesystem(path)
      .then((data) => setBrowse(data))
      .catch(() => {});
  }

  const selectedBytes = useMemo(
    () =>
      files
        .filter((file) => checked.has(file.relative_path))
        .reduce((sum, file) => sum + file.size_bytes, 0),
    [files, checked],
  );

  async function handleCreateProfile(): Promise<void> {
    const name = newProfileName.trim();
    if (name === "") {
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const profile = await createFilmiumShareProfile({
        name,
        default_destination_folder: newProfileDest.trim() || "VIDEOS",
      });
      setProfiles((prev) => [...prev, profile]);
      setSelectedProfileId(profile.id);
      setCreatingProfile(false);
      setNewProfileName("");
      setStatus(`Profil „${profile.name}" napravljen.`);
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "Profil nije napravljen.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAddToProfile(): Promise<void> {
    if (selectedProfileId === null || checked.size === 0) {
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      await addToFilmiumShareQueue(
        selectedProfileId,
        mediaId,
        checked.size === files.length ? "complete" : "playback",
      );
      window.localStorage.setItem(
        LAST_PROFILE_KEY,
        String(selectedProfileId),
      );
      const name =
        profiles.find((profile) => profile.id === selectedProfileId)?.name
        ?? "profil";
      setStatus(`Dodato u profil „${name}".`);
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : "Dodavanje u profil nije uspelo.",
      );
    } finally {
      setBusy(false);
    }
  }

  /**
   * Native izbor foldera (Windows explorer) → zaključava odredište.
   */
  function handleDirPick(fileList: FileList | null): void {
    if (!fileList || fileList.length === 0) {
      return;
    }
    const first = fileList[0] as File & { path?: string };
    const relative = first.webkitRelativePath ?? "";
    const absolute = first.path;

    if (absolute && relative) {
      const separator = absolute.includes("\\") ? "\\" : "/";
      const relativeOs = relative.split("/").join(separator);
      if (absolute.endsWith(relativeOs)) {
        const parent = absolute
          .slice(0, absolute.length - relativeOs.length)
          .replace(/[\\/]$/, "");
        const top = relative.split("/")[0];
        const dest = `${parent}${separator}${top}`;
        lockDestination(dest);
        setStatus(`Odredište zaključano: ${dest}`);
        return;
      }
    }
    setStatus(
      "Nije moguće očitati putanju foldera — koristi diskove/navigator ispod.",
    );
  }

  async function handleTransfer(): Promise<void> {
    if (!destination || checked.size === 0) {
      return;
    }
    setBusy(true);
    setStatus(null);
    setDone(false);
    setProgress({
      files_done: 0,
      files_total: checked.size,
      file_done: 0,
      file_total: 0,
    });
    try {
      // Uvek eksplicitna lista štikliranih (uključuje prevode/slike/ostalo),
      // da se ne kopiraju samo indeksirani fajlovi.
      const relativePaths = Array.from(checked);
      const result = await transferFilmiumMediaStream(
        mediaId,
        destination,
        relativePaths,
        (value) => setProgress(value),
      );
      rememberLocation(destination);
      setDone(true);
      playSound("completed");
      setStatus(
        `Preneseno ${result.copied_files} fajlova `
        + `(${formatBytes(result.total_bytes)}) → ${result.destination}`,
      );
    } catch (error) {
      playSound("error");
      setStatus(
        error instanceof Error ? error.message : "Prenos nije uspeo.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="filmium-transfer-overlay"
      onClick={onClose}
      role="presentation"
    >
      <aside
        aria-label="Prebaci sadržaj"
        className="filmium-transfer-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="filmium-transfer-head">
          <div className="filmium-editor-header-title">
            <span className="filmium-editor-header-icon">
              <Send size={18} />
            </span>
            <div>
              <h2>Prebaci</h2>
              <p>{title}</p>
            </div>
          </div>
          <button
            className="filmium-editor-button ghost"
            onClick={onClose}
            type="button"
          >
            <X size={16} />
            Zatvori
          </button>
        </header>

        {status && (
          <p className="filmium-editor-enrich-message">{status}</p>
        )}

        <div className="filmium-transfer-body">
          {/* ----------  LEVO: STABLO FAJLOVA  ---------- */}

          <section className="filmium-transfer-tree">
            {/* ----------  PROFILI  ---------- */}

            <div className="filmium-transfer-profile">
              <p className="filmium-editor-block-label">
                <Users size={13} /> PROFIL
              </p>
              <div className="filmium-transfer-profile-row">
                <select
                  className="filmium-editor-input"
                  onChange={(event) =>
                    setSelectedProfileId(
                      event.target.value
                        ? Number(event.target.value)
                        : null,
                    )}
                  value={selectedProfileId ?? ""}
                >
                  <option value="">— izaberi profil —</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
                <button
                  className="filmium-editor-button primary small"
                  disabled={
                    busy || selectedProfileId === null || checked.size === 0
                  }
                  onClick={() => void handleAddToProfile()}
                  type="button"
                >
                  <UserPlus size={13} />
                  Dodaj u profil
                </button>
                <button
                  className="filmium-editor-button ghost small"
                  onClick={() => setCreatingProfile((open) => !open)}
                  type="button"
                >
                  <Plus size={13} />
                  Napravi profil
                </button>
              </div>

              {creatingProfile && (
                <div className="filmium-transfer-profile-create">
                  <input
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setNewProfileName(event.target.value)}
                    placeholder="Naziv profila (npr. Deki)"
                    value={newProfileName}
                  />
                  <input
                    className="filmium-editor-input"
                    onChange={(event) =>
                      setNewProfileDest(event.target.value)}
                    placeholder="Podrazumevani folder (VIDEOS)"
                    value={newProfileDest}
                  />
                  <button
                    className="filmium-editor-button primary small"
                    disabled={busy || newProfileName.trim() === ""}
                    onClick={() => void handleCreateProfile()}
                    type="button"
                  >
                    Sačuvaj profil
                  </button>
                </div>
              )}
            </div>

            <div className="filmium-transfer-tree-head">
              <p className="filmium-editor-block-label">
                FAJLOVI ZA PRENOS
              </p>
              <label className="filmium-editor-toggle">
                <input
                  checked={allChecked}
                  onChange={toggleAll}
                  type="checkbox"
                />
                Svi
              </label>
            </div>

            <div className="filmium-transfer-file-list">
              {files.length === 0 && (
                <p className="filmium-media-empty">
                  Nema registrovanih fajlova za ovaj sadržaj.
                </p>
              )}
              {GROUP_ORDER.filter((role) => groupedFiles.has(role)).map(
                (role) => {
                  const groupFiles = groupedFiles.get(role) ?? [];
                  const open = isGroupOpen(role);
                  const allOn = groupFiles.every((file) =>
                    checked.has(file.relative_path),
                  );
                  return (
                    <div className="filmium-transfer-group" key={role}>
                      <div className="filmium-transfer-group-head">
                        <button
                          className="filmium-transfer-group-toggle"
                          onClick={() => toggleGroup(role)}
                          type="button"
                        >
                          {open ? (
                            <ChevronDown size={14} />
                          ) : (
                            <ChevronRight size={14} />
                          )}
                          <Folder size={14} />
                          <span>{GROUP_LABEL[role]}</span>
                          <em>{groupFiles.length}</em>
                        </button>
                        <label
                          className="filmium-editor-toggle"
                          title="Štikliraj sve u grupi"
                        >
                          <input
                            checked={allOn}
                            onChange={() => toggleGroupFiles(groupFiles)}
                            type="checkbox"
                          />
                        </label>
                      </div>
                      {open && (
                        <div className="filmium-transfer-group-files">
                          {groupFiles.map((file) => (
                            <label
                              className="filmium-transfer-file"
                              key={file.relative_path}
                            >
                              <input
                                checked={checked.has(file.relative_path)}
                                onChange={() =>
                                  toggleFile(file.relative_path)}
                                type="checkbox"
                              />
                              <span className="filmium-transfer-file-name">
                                {file.relative_path}
                              </span>
                              <span className="filmium-transfer-file-size">
                                {formatBytes(file.size_bytes)}
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                },
              )}
            </div>
          </section>

          {/* ----------  DESNO: ODREDIŠTE  ---------- */}

          <aside className="filmium-transfer-dest">
            <input
              hidden
              onChange={(event) => {
                handleDirPick(event.target.files);
                event.target.value = "";
              }}
              ref={dirInputRef}
              type="file"
            />

            {/* ----------  DISKOVI (dropdown)  ---------- */}

            <p className="filmium-editor-block-label">
              <HardDrive size={13} /> DISK
            </p>
            <select
              className="filmium-editor-input"
              onChange={(event) => {
                if (event.target.value) {
                  openFolder(event.target.value);
                }
              }}
              value={browse?.path ?? ""}
            >
              <option value="">— izaberi disk —</option>
              {disks.map((disk) => (
                <option key={disk.path} value={disk.path}>
                  {disk.label} ({formatBytes(disk.free_bytes)} slobodno)
                </option>
              ))}
            </select>

            {/* ----------  NEDAVNE LOKACIJE  ---------- */}

            <p className="filmium-editor-block-label">
              <Clock size={13} /> NEDAVNE LOKACIJE
            </p>
            <div className="filmium-transfer-recent">
              {recent.map((path) => (
                <button
                  className={`filmium-transfer-recent-item${
                    destination === path ? " active" : ""
                  }`}
                  key={path}
                  onClick={() => lockDestination(path)}
                  type="button"
                >
                  <Folder size={14} />
                  <span>{path}</span>
                </button>
              ))}
              {recent.length === 0 && (
                <p className="filmium-media-empty">
                  Još nema korišćenih lokacija.
                </p>
              )}
            </div>

            {/* ----------  NAVIGATOR + IZBOR  ---------- */}

            <div className="filmium-transfer-browser">
              <div className="filmium-transfer-browser-bar">
                <button
                  className="filmium-editor-button ghost small"
                  disabled={!browse?.parent && !browse?.path}
                  onClick={() => openFolder(browse?.parent ?? undefined)}
                  type="button"
                >
                  <ChevronLeft size={13} />
                  Nazad
                </button>
                <code>{browse?.path ?? "Izaberi disk"}</code>
              </div>

              <div className="filmium-transfer-folders">
                {(browse?.directories ?? []).map((entry) => (
                  <div
                    className={`filmium-transfer-folder-row${
                      destination === entry.path ? " active" : ""
                    }`}
                    key={entry.path}
                  >
                    <button
                      className="filmium-transfer-folder-select"
                      onClick={() => lockDestination(entry.path)}
                      onDoubleClick={() => openFolder(entry.path)}
                      title={
                        "Klik: izaberi kao odredište · dupli klik: uđi"
                      }
                      type="button"
                    >
                      <Folder size={14} />
                      <span>{entry.name}</span>
                      {destination === entry.path && (
                        <Check
                          className="filmium-transfer-folder-check"
                          size={14}
                        />
                      )}
                    </button>
                    <button
                      aria-label={`Uđi u ${entry.name}`}
                      className="filmium-transfer-folder-enter"
                      onClick={() => openFolder(entry.path)}
                      title="Uđi u folder"
                      type="button"
                    >
                      <ChevronRight size={15} />
                    </button>
                  </div>
                ))}
                {browse && browse.directories.length === 0 && (
                  <p className="filmium-media-empty">Nema pod-foldera.</p>
                )}
              </div>
            </div>

            <button
              className={`filmium-editor-button small full${
                destination && destination === browse?.path
                  ? " success"
                  : " ghost"
              }`}
              disabled={!browse?.path}
              onClick={() => lockDestination(browse?.path ?? "")}
              type="button"
            >
              <Lock size={13} />
              Izaberi trenutni folder
            </button>

            <button
              className="filmium-editor-button ghost small full"
              onClick={() => dirInputRef.current?.click()}
              type="button"
            >
              <FolderSearch size={13} />
              Izaberi Direktorij (explorer)
            </button>

            {/* ----------  SAŽETAK + PROGRES + PRENOS  ---------- */}

            <div className="filmium-transfer-summary">
              <div className="filmium-files-detail-row">
                <span>Odredište</span>
                <strong
                  className={`mono filmium-transfer-dest-value${
                    destination ? " set" : ""
                  }`}
                >
                  {destination ?? "— izaberi folder —"}
                </strong>
              </div>
              <div className="filmium-files-detail-row">
                <span>Izabrano</span>
                <strong>
                  {checked.size} fajl(ova) · {formatBytes(selectedBytes)}
                </strong>
              </div>
            </div>

            {(busy || progress) && (
              <div className="filmium-transfer-progress">
                <div className="filmium-transfer-progress-track">
                  <div
                    className="filmium-transfer-progress-fill"
                    style={{
                      width: `${progress ? sseOverallPercent(progress) : 0}%`,
                    }}
                  />
                </div>
                <span>
                  {progress
                    ? `${progress.files_done} / ${progress.files_total} fajlova`
                    : "Pripremam…"}
                </span>
              </div>
            )}

            <button
              className={`filmium-editor-button full ${
                done ? "success" : "primary"
              }`}
              disabled={busy || !destination || checked.size === 0}
              onClick={() => void handleTransfer()}
              type="button"
            >
              {busy ? (
                <Loader className="spinning" size={15} />
              ) : done ? (
                <Check size={15} />
              ) : (
                <Send size={15} />
              )}
              {busy
                ? "Kopiram…"
                : done
                  ? "Preneseno ✓"
                  : "Prenesi (kopiraj)"}
            </button>
          </aside>
        </div>
      </aside>
    </div>
  );
}

export default FilmiumTransferPanel;
