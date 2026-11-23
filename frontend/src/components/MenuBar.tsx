import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export type MenuEntry =
  | { type: "item"; label: string; onClick: () => void; disabled?: boolean; hint?: string; checked?: boolean }
  | { type: "header"; label: string }
  | { type: "separator" };

export interface MenuDef {
  label: string;
  entries: MenuEntry[];
  disabled?: boolean;
}

interface Props {
  menus: MenuDef[];
  label?: string;
  buttonIcon?: ReactNode;
}

export default function MenuBar({ menus, label = "Меню приложения", buttonIcon }: Props) {
  const [open, setOpen] = useState<number | null>(null);
  const barRef = useRef<HTMLDivElement | null>(null);
  const buttonsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Закрытие по клику вне меню и по Escape.
  useEffect(() => {
    if (open === null) return;

    const onPointer = (event: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(event.target as Node)) {
        setOpen(null);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(null);
        if (barRef.current?.contains(document.activeElement)) buttonsRef.current[open]?.focus();
      }
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={`menubar${buttonIcon ? " menubar-action" : ""}`} ref={barRef}
      role="group" aria-label={label}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(null); }}>
      {menus.map((menu, index) => (
        <div className="menu" key={menu.label}>
          <button
            type="button"
            aria-expanded={open === index}
            disabled={menu.disabled}
            ref={(element) => { buttonsRef.current[index] = element; }}
            className={`menu-button${open === index ? " open" : ""}`}
            onClick={() => setOpen(open === index ? null : index)}
            onMouseEnter={() => open !== null && setOpen(index)}
          >
            {buttonIcon}{menu.label}{buttonIcon && <ChevronDown size={13} aria-hidden="true" />}
          </button>

          {open === index && (
            <div className="menu-list" role="group" aria-label={menu.label}>
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
                    className="menu-item"
                    disabled={entry.disabled}
                    onClick={() => {
                      setOpen(null);
                      entry.onClick();
                    }}
                  >
                    <span className="menu-check" aria-hidden="true">{entry.checked ? "✓" : ""}</span>
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
