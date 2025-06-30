import React, { useEffect, useState } from "react";
import { fetchClasses, updateClass, bulkUpdateClasses } from "./api/classApi";
import Header from "./Header.js";
import styles from "./AdminDashboard.module.css";

const AdminDashboard = () => {
  const [classes, setClasses] = useState([]);
  const [edited, setEdited] = useState({});
  const [bulkText, setBulkText] = useState("");
  const [message, setMessage] = useState("");
  const [changedIds, setChangedIds] = useState(new Set()); // track which rows changed

  useEffect(() => {
    fetchClasses()
      .then((res) => {
        setClasses(res.data);
        setEdited(Object.fromEntries(res.data.map((c) => [c.id, c.name])));
      })
      .catch(() => setMessage("Failed to load classes"));
  }, []);

  const saveAll = async () => {
    const updates = Array.from(changedIds).map((id) =>
      updateClass(id, edited[id])
    );
    try {
      await Promise.all(updates);
      setMessage("All changes saved");
      setChangedIds(new Set());
      const res = await fetchClasses();
      setClasses(res.data);
      setEdited(Object.fromEntries(res.data.map((c) => [c.id, c.name])));
    } catch {
      setMessage("Error saving changes");
    }
  };

  const clearChanges = () => {
    setEdited(Object.fromEntries(classes.map((c) => [c.id, c.name])));
    setChangedIds(new Set());
    setMessage("");
  };

  const saveBulk = async () => {
    const names = bulkText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    if (!names.length) {
      setMessage("Please enter at least one class name (comma-separated).");
      return;
    }
    if (names.length !== classes.length) {
      setMessage(
        `Expected ${classes.length} names but got ${names.length}. ` +
          "Please provide all class names in a comma-separated list."
      );
      return;
    }

    try {
      const res = await bulkUpdateClasses(names);
      setClasses(res.data);
      setEdited(Object.fromEntries(res.data.map((c) => [c.id, c.name])));
      setMessage("Bulk update successful");
    } catch {
      setMessage("Error saving bulk changes");
    }
  };

  return (
    <>
      <Header activeLink="home" showNotification={false} />
      <div className={styles.container}>
        <h1 className={styles.title}>Class Management</h1>

        <div className={styles.actions}>
          <button
            className={styles.button}
            disabled={changedIds.size === 0}
            onClick={saveAll}
          >
            Save All
          </button>
          <button
            className={styles.button}
            disabled={changedIds.size === 0}
            onClick={clearChanges}
          >
            Clear Selection
          </button>
        </div>

        {message && <div className={styles.message}>{message}</div>}
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((c) => (
              <tr
                key={c.id}
                className={changedIds.has(c.id) ? styles.editedRow : ""}
              >
                <td>{c.id}</td>
                <td>
                  <input
                    className={styles.input}
                    value={edited[c.id] || ""}
                    onChange={(e) => {
                      setEdited({ ...edited, [c.id]: e.target.value });
                      setChangedIds((prev) => new Set(prev).add(c.id));
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className={styles.bulkSection}>
          <h2 className={styles.title}>Bulk Update</h2>
          <p>
            Paste a comma-separated list of <strong>{classes.length}</strong>{" "}
            class names (in ID order).
          </p>
          <textarea
            className={styles.textarea}
            placeholder="e.g. Class1, Class2, Class3, …"
            value={bulkText}
            onChange={(e) => {
              setBulkText(e.target.value);
              setMessage("");
            }}
          />
          <button className={styles.button} onClick={saveBulk}>
            Submit Bulk
          </button>
        </div>
      </div>
    </>
  );
};

export default AdminDashboard;
