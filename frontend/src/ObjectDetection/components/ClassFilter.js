import React, { useEffect, useRef, useState, useCallback } from "react";
import { getClasses } from "../api/imageApi";
import styles from "./styles.module.css";

const ClassFilter = ({
  onSearch,
  onClassSelect,
  selectedClass,
  setClassList,
  onBoxCountFilterChange,
  selectedBoxCountFilter,
}) => {
  const [isDropdownOpen, setDropdownOpen] = useState(false);
  const [activeSubMenu, setActiveSubMenu] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [classListLocal, setClassListLocal] = useState([]);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const filterAreaRef = useRef(null);
  const speciesListRef = useRef(null);
  const highlightedRef = useRef(null);
  const [searchText, setSearchText] = useState("");

  const [boxOperator, setBoxOperator] = useState(">");
  const [boxValue, setBoxValue] = useState("");
  const [boxCountSubmenuOpen, setBoxCountSubmenuOpen] = useState(false);

  const displayClassList = [{ id: "All", name: "All" }, ...classListLocal];

  useEffect(() => {
    const fetchClasses = async () => {
      try {
        const classes = await getClasses();
        const actualClasses = classes.filter(
          (cls) => cls.id !== "All" && cls.name.toLowerCase() !== "all"
        );
        setClassListLocal(actualClasses);
        setClassList(actualClasses);
      } catch (error) {
        console.error("Error fetching classes:", error);
      }
    };

    fetchClasses();
  }, [setClassList]);

  const closeMenus = useCallback(() => {
    setDropdownOpen(false);
    setActiveSubMenu(null);
    setSearchQuery("");
    setHighlightedIndex(-1);
    setBoxCountSubmenuOpen(false);
  }, []);

  const handleClassSelect = useCallback(
    (classOption) => {
      onClassSelect(classOption.id);
      closeMenus();
    },
    [onClassSelect, closeMenus]
  );

  const applyBoxCountFilter = useCallback(() => {
    if (boxValue === "" || isNaN(parseInt(boxValue, 10))) {
      onBoxCountFilterChange(null);
    } else {
      const filterString = `${boxOperator}${parseInt(boxValue, 10)}`;
      onBoxCountFilterChange(filterString);
    }
    closeMenus();
  }, [boxOperator, boxValue, onBoxCountFilterChange, closeMenus]);

  const clearBoxCountFilter = useCallback(() => {
    setBoxValue("");
    onBoxCountFilterChange(null);
    closeMenus();
  }, [onBoxCountFilterChange, closeMenus]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        filterAreaRef.current &&
        !filterAreaRef.current.contains(event.target)
      ) {
        closeMenus();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [closeMenus]);

  const filteredSpecies = displayClassList.filter(
    (option) =>
      option.id !== "All" &&
      option.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSpeciesKeyDown = (e) => {
    if (activeSubMenu !== "species") return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prevIndex) =>
        prevIndex < filteredSpecies.length - 1 ? prevIndex + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prevIndex) =>
        prevIndex > 0 ? prevIndex - 1 : filteredSpecies.length - 1
      );
    } else if (e.key === "Enter" && highlightedIndex !== -1) {
      e.preventDefault();
      handleClassSelect(filteredSpecies[highlightedIndex]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeMenus();
    }
  };

  useEffect(() => {
    if (highlightedRef.current) {
      highlightedRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [highlightedIndex, activeSubMenu]);

  useEffect(() => {
    if (activeSubMenu === "species" && speciesListRef.current) {
      const input = speciesListRef.current.querySelector("input");
      if (input) {
        input.focus();
      }
    }
  }, [activeSubMenu]);

  const selectedClassName =
    selectedClass !== "All"
      ? displayClassList.find((opt) => String(opt.id) === String(selectedClass))
          ?.name
      : null;

  let boxFilterDisplay = null;
  if (selectedBoxCountFilter) {
    const match = selectedBoxCountFilter.match(/([=><])(\d+)/);
    if (match) {
      boxFilterDisplay = `Boxes ${match[1]} ${match[2]}`;
    }
  }

  return (
    <div className={styles["navigation-container"]}>
      {onSearch && (
        <input
          type="text"
          className={styles["search-input"]}
          placeholder="Search images..."
          value={searchText}
          onChange={(e) => {
            setSearchText(e.target.value);
            onSearch(e.target.value);
          }}
        />
      )}
      <div className={styles["filter-area"]} ref={filterAreaRef}>
        <button
          onClick={() => {
            setDropdownOpen(!isDropdownOpen);
            if (isDropdownOpen) setActiveSubMenu(null);
          }}
          className={styles["filter-button"]}
        >
          Filter
          <span
            className={`${styles["arrow"]} ${
              isDropdownOpen ? styles["up"] : styles["down"]
            }`}
          >
            ▼
          </span>
        </button>

        <div className={styles["selected-filters-container"]}>
          {selectedClassName && (
            <span className={styles["filter-tag"]}>
              Species: {selectedClassName}
              <button
                onClick={() => handleClassSelect({ id: "All", name: "All" })}
                className={styles["remove-tag-button"]}
                title="Remove species filter"
              >
                &times;
              </button>
            </span>
          )}
          {boxFilterDisplay && (
            <span className={styles["filter-tag"]}>
              {boxFilterDisplay}
              <button
                onClick={clearBoxCountFilter}
                className={styles["remove-tag-button"]}
                title="Remove box count filter"
              >
                &times;
              </button>
            </span>
          )}
        </div>

        {isDropdownOpen && (
          <div className={styles["dropdown-menu"]}>
            <button
              className={`${styles["category-option"]} ${
                activeSubMenu === "species" ? styles["active"] : ""
              }`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveSubMenu(
                  activeSubMenu === "species" ? null : "species"
                );
                setBoxCountSubmenuOpen(false);
                setHighlightedIndex(-1);
              }}
            >
              Species
              <span className={styles["submenu-arrow"]}>&rarr;</span>
            </button>

            <button
              className={`${styles["category-option"]} ${
                activeSubMenu === "boxCount" ? styles["active"] : ""
              }`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveSubMenu(
                  activeSubMenu === "boxCount" ? null : "boxCount"
                );
                setBoxCountSubmenuOpen(activeSubMenu !== "boxCount");
              }}
            >
              Box Count
              <span className={styles["submenu-arrow"]}>&rarr;</span>
            </button>

            {activeSubMenu === "species" && (
              <div
                className={styles["side-menu"]}
                ref={speciesListRef}
                onClick={(e) => e.stopPropagation()}
              >
                <div className={styles["search-container-side"]}>
                  <input
                    type="text"
                    placeholder="Search species..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setHighlightedIndex(-1);
                    }}
                    className={styles["search-input-side"]}
                    onKeyDown={handleSpeciesKeyDown}
                  />
                </div>
                <div
                  className={styles["class-list-side"]}
                  tabIndex={-1}
                  onKeyDown={handleSpeciesKeyDown}
                >
                  <button
                    key="All"
                    onClick={() =>
                      handleClassSelect({ id: "All", name: "All" })
                    }
                    className={`${styles["class-option-side"]} ${
                      selectedClass === "All" ? styles["selected"] : ""
                    } ${
                      highlightedIndex === -1 && searchQuery === ""
                        ? styles["highlighted"]
                        : ""
                    }`}
                    ref={
                      highlightedIndex === -1 && searchQuery === ""
                        ? highlightedRef
                        : null
                    }
                  >
                    All Species
                  </button>
                  {filteredSpecies.map((classOption, index) => (
                    <button
                      key={classOption.id}
                      onClick={() => handleClassSelect(classOption)}
                      className={`${styles["class-option-side"]} ${
                        selectedClass === classOption.id
                          ? styles["selected"]
                          : ""
                      } ${
                        index === highlightedIndex ? styles["highlighted"] : ""
                      }`}
                      ref={index === highlightedIndex ? highlightedRef : null}
                    >
                      {classOption.name}
                    </button>
                  ))}
                  {filteredSpecies.length === 0 && searchQuery !== "" && (
                    <div className={styles["no-results-side"]}>
                      No matching species
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeSubMenu === "boxCount" && boxCountSubmenuOpen && (
              <div
                className={styles["side-menu"]}
                onClick={(e) => e.stopPropagation()}
              >
                <div className={styles["box-count-filter-controls"]}>
                  <select
                    value={boxOperator}
                    onChange={(e) => setBoxOperator(e.target.value)}
                    className={styles["box-count-select"]}
                  >
                    <option value=">">&gt;</option>
                    <option value="<">&lt;</option>
                    <option value="=">=</option>
                  </select>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    placeholder="Count"
                    value={boxValue}
                    onChange={(e) => setBoxValue(e.target.value)}
                    className={styles["box-count-input"]}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") applyBoxCountFilter();
                    }}
                  />
                  <button
                    onClick={applyBoxCountFilter}
                    className={styles["box-count-apply-button"]}
                  >
                    Apply
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ClassFilter;
