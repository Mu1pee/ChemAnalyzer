import { useEffect, useRef, useState } from "react";
import { IconLogo } from "./Icons";

export type MenuEntry =
  | { type: "item"; label: string; onClick: () => void; disabled?: boolean; hint?: string; checked?: boolean }
  | { type: "header"; label: string }
  | { type: "separator" };

export interface MenuDef {
  label: string;
  entries: MenuEntry[];
}

interface Props {
  menus: MenuDef[];
}

export default function MenuBar({ menus }: Props) {
  const [open, setOpen] = useState<number | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);

  // Закрытие по клику вне меню и по Escape.
  useEffect(() => {
    if (open === null) return;

    const onPointer = (event: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(event.target as Node)) {
        setOpen(null);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="menubar" ref={barRef} role="menubar">
      <div className="menubar-brand">
        <IconLogo size={20} />
        <strong>ChemAnalyzer</strong>
      </div>

      {menus.map((menu, index) => (
        <div className="menu" key={menu.label}>
          <button
            type="button"
            role="menuitem"
            aria-haspopup="true"
            aria-expanded={open === index}
            className={`menu-button${open === index ? " open" : ""}`}
            onClick={() => setOpen(open === index ? null : index)}
            onMouseEnter={() => open !== null && setOpen(index)}
          >
            {menu.label}
          </button>

          {open === index && (
            <div className="menu-list" role="menu">
              {menu.entries.map((entry, i) => {
                if (entry.type === "separator") {
                  return <div className="menu-sep" key={i} role="separator" />;
                }
                if (entry.type === "header") {
                  return (
                    <div className="menu-header" key={i}>
                      {entry.label}
                    </div>
                  );
                }
                return (
                  <button
                    key={i}
                    type="button"
                    role="menuitem"
                    className="menu-item"
                    disabled={entry.disabled}
                    onClick={() => {
                      setOpen(null);
                      entry.onClick();
                    }}
                  >
                    <span className="menu-check">{entry.checked ? "✓" : ""}</span>
                    <span className="menu-label">{entry.label}</span>
                    {entry.hint && <span className="menu-hint">{entry.hint}</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
