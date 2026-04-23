import { createContext, useContext, useReducer, useCallback } from "react";

const TrayContext = createContext(null);

const initial = { selected: new Set() };

function reducer(state, action) {
  switch (action.type) {
    case "toggle": {
      const s = new Set(state.selected);
      if (s.has(action.id)) s.delete(action.id);
      else s.add(action.id);
      return { selected: s };
    }
    case "add": {
      const s = new Set(state.selected);
      s.add(action.id);
      return { selected: s };
    }
    case "remove": {
      const s = new Set(state.selected);
      s.delete(action.id);
      return { selected: s };
    }
    case "clear":
      return { selected: new Set() };
    default:
      return state;
  }
}

export function TrayProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const toggle = useCallback((id) => dispatch({ type: "toggle", id }), []);
  const add = useCallback((id) => dispatch({ type: "add", id }), []);
  const remove = useCallback((id) => dispatch({ type: "remove", id }), []);
  const clear = useCallback(() => dispatch({ type: "clear" }), []);
  const isSelected = useCallback((id) => state.selected.has(id), [state.selected]);
  return (
    <TrayContext.Provider
      value={{ selected: state.selected, toggle, add, remove, clear, isSelected }}
    >
      {children}
    </TrayContext.Provider>
  );
}

export const useTray = () => {
  const ctx = useContext(TrayContext);
  if (!ctx) throw new Error("useTray must be used inside TrayProvider");
  return ctx;
};
