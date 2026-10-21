import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ApiClientError,
  API_BASE_URL,
  createItem,
  fetchItems,
  restoreItemMaintenance,
  setItemMaintenance,
} from "./api/client";
import type { ItemCreate, ItemListParams, ItemResponse, ItemStatus } from "./api/types";
import {
  formatPaise,
  isMaintenanceActionAllowed,
  type ItemFormValues,
  validateItemForm,
} from "./api/utils";

const PAGE_SIZE = 10;

const STATUS_OPTIONS: { value: ItemStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "AVAILABLE", label: "Available" },
  { value: "RESERVED", label: "Reserved" },
  { value: "CHECKED_OUT", label: "Checked Out" },
  { value: "UNDER_MAINTENANCE", label: "Under Maintenance" },
];

function getStatusBadgeClass(status: ItemStatus): string {
  switch (status) {
    case "AVAILABLE":
      return "status-badge status-available";
    case "RESERVED":
      return "status-badge status-reserved";
    case "CHECKED_OUT":
      return "status-badge status-checked-out";
    case "UNDER_MAINTENANCE":
      return "status-badge status-under-maintenance";
    default:
      return "status-badge";
  }
}

function getStatusLabel(status: ItemStatus): string {
  switch (status) {
    case "AVAILABLE":
      return "Available";
    case "RESERVED":
      return "Reserved";
    case "CHECKED_OUT":
      return "Checked Out";
    case "UNDER_MAINTENANCE":
      return "Under Maintenance";
    default:
      return status;
  }
}

interface NotificationState {
  type: "success" | "error";
  message: string;
}

export default function App() {
  const searchInputId = useId();
  const categorySelectId = useId();
  const statusSelectId = useId();

  // Filters and search
  const [searchInput, setSearchInput] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<ItemStatus | "">("");

  // Pagination & data
  const [page, setPage] = useState<number>(0);
  const [items, setItems] = useState<ItemResponse[]>([]);
  const [hasNextPage, setHasNextPage] = useState<boolean>(false);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);

  // UI state
  const [initialLoading, setInitialLoading] = useState<boolean>(true);
  const [isFetching, setIsFetching] = useState<boolean>(false);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [error, setError] = useState<ApiClientError | Error | null>(null);

  // Global notification banner (success / action error)
  const [notification, setNotification] = useState<NotificationState | null>(null);

  // Action loading indicator per item ID
  const [actionInProgressId, setActionInProgressId] = useState<number | null>(null);

  // Add Item Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [formValues, setFormValues] = useState<ItemFormValues>({
    name: "",
    category: "",
    replacement_value: "",
    condition_note: "",
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [isSubmittingItem, setIsSubmittingItem] = useState<boolean>(false);
  const [formApiError, setFormApiError] = useState<string | null>(null);

  const nameInputRef = useRef<HTMLInputElement>(null);

  // Auto-focus Name input when modal opens
  useEffect(() => {
    if (isAddModalOpen) {
      const timer = setTimeout(() => {
        nameInputRef.current?.focus();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [isAddModalOpen]);

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isAddModalOpen && !isSubmittingItem) {
        handleCloseModal();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isAddModalOpen, isSubmittingItem]);

  // Auto-dismiss notification after 6 seconds
  useEffect(() => {
    if (!notification) return;
    const timer = setTimeout(() => {
      setNotification(null);
    }, 6000);
    return () => clearTimeout(timer);
  }, [notification]);

  // Debounce search query input (300ms)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchInput]);

  // Handle category selection
  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCategory(e.target.value);
    setPage(0);
  };

  // Handle status selection
  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedStatus(e.target.value as ItemStatus | "");
    setPage(0);
  };

  // Reset all filters
  const handleResetFilters = () => {
    setSearchInput("");
    setDebouncedQuery("");
    setSelectedCategory("");
    setSelectedStatus("");
    setPage(0);
  };

  // Manual refresh
  const handleRefresh = useCallback(() => {
    if (isFetching) return;
    setRefreshTrigger((prev) => prev + 1);
  }, [isFetching]);

  // Load available categories on initial mount and when explicitly refreshed
  useEffect(() => {
    const controller = new AbortController();

    fetchItems({ limit: 500 }, { signal: controller.signal })
      .then((allItems) => {
        const uniqueCategories = Array.from(
          new Set(
            allItems
              .map((item) => item.category?.trim())
              .filter((cat): cat is string => Boolean(cat)),
          ),
        ).sort((a, b) => a.localeCompare(b));
        setAvailableCategories(uniqueCategories);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        // Non-critical: failure to preload full category list will not block item browsing
      });

    return () => controller.abort();
  }, [refreshTrigger]);

  // Fetch paginated items whenever filters, search, page, or refresh trigger changes
  useEffect(() => {
    const controller = new AbortController();
    setIsFetching(true);
    setError(null);

    const params: ItemListParams = {
      limit: PAGE_SIZE + 1,
      offset: page * PAGE_SIZE,
    };

    if (debouncedQuery) {
      params.q = debouncedQuery;
    }
    if (selectedCategory) {
      params.category = selectedCategory;
    }
    if (selectedStatus) {
      params.status = selectedStatus;
    }

    fetchItems(params, { signal: controller.signal })
      .then((fetchedItems) => {
        if (controller.signal.aborted) return;

        if (fetchedItems.length > PAGE_SIZE) {
          setHasNextPage(true);
          setItems(fetchedItems.slice(0, PAGE_SIZE));
        } else {
          setHasNextPage(false);
          setItems(fetchedItems);
        }

        // Dynamically incorporate any newly discovered categories
        const newCats = fetchedItems
          .map((i) => i.category?.trim())
          .filter((cat): cat is string => Boolean(cat));
        if (newCats.length > 0) {
          setAvailableCategories((prev) =>
            Array.from(new Set([...prev, ...newCats])).sort((a, b) =>
              a.localeCompare(b),
            ),
          );
        }

        setInitialLoading(false);
        setIsFetching(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        setInitialLoading(false);
        setIsFetching(false);
      });

    return () => controller.abort();
  }, [debouncedQuery, selectedCategory, selectedStatus, page, refreshTrigger]);

  // ============================================================================
  // Item Creation Handlers
  // ============================================================================

  const handleOpenModal = () => {
    setFormValues({ name: "", category: "", replacement_value: "", condition_note: "" });
    setFormErrors({});
    setFormApiError(null);
    setIsAddModalOpen(true);
  };

  const handleCloseModal = () => {
    if (isSubmittingItem) return;
    setIsAddModalOpen(false);
    setFormErrors({});
    setFormApiError(null);
  };

  const handleFormFieldChange = (
    field: keyof ItemFormValues,
    value: string,
  ) => {
    setFormValues((prev) => ({ ...prev, [field]: value }));
    // Clear field-specific error as user types
    if (formErrors[field]) {
      setFormErrors((prev) => {
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    }
    if (formApiError) {
      setFormApiError(null);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormApiError(null);

    const validation = validateItemForm(formValues);
    if (!validation.isValid || validation.parsedPaise === undefined) {
      setFormErrors(validation.errors);
      return;
    }

    setFormErrors({});
    setIsSubmittingItem(true);

    try {
      const payload: ItemCreate = {
        name: formValues.name.trim(),
        category: formValues.category.trim(),
        replacement_value: validation.parsedPaise,
        condition_note: formValues.condition_note?.trim() || null,
      };

      const newItem = await createItem(payload);
      handleCloseModal();
      setNotification({
        type: "success",
        message: `Successfully created equipment item "${newItem.name}" (#${newItem.id}) in Available status.`,
      });
      // Trigger catalogue and category refresh
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setFormApiError(err.message);
      } else {
        setFormApiError("An unexpected error occurred while creating the equipment item.");
      }
    } finally {
      setIsSubmittingItem(false);
    }
  };

  // ============================================================================
  // Maintenance Action Handlers
  // ============================================================================

  const handleSetMaintenance = async (item: ItemResponse) => {
    if (actionInProgressId !== null) return;
    setActionInProgressId(item.id);

    try {
      const updated = await setItemMaintenance(item.id);
      setNotification({
        type: "success",
        message: `Item #${updated.id} ("${updated.name}") has been marked as Under Maintenance.`,
      });
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const detail =
        err instanceof ApiClientError
          ? `${err.error}: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to place item under maintenance.";
      setNotification({
        type: "error",
        message: `Failed to place item #${item.id} under maintenance. ${detail}`,
      });
      // Refresh to ensure client displays actual backend state
      setRefreshTrigger((prev) => prev + 1);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleRestoreMaintenance = async (item: ItemResponse) => {
    if (actionInProgressId !== null) return;
    setActionInProgressId(item.id);

    try {
      const updated = await restoreItemMaintenance(item.id);
      setNotification({
        type: "success",
        message: `Item #${updated.id} ("${updated.name}") has been restored to service (${getStatusLabel(updated.status)}).`,
      });
      setRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const detail =
        err instanceof ApiClientError
          ? `${err.error}: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to restore item to service.";
      setNotification({
        type: "error",
        message: `Failed to restore item #${item.id} to service. ${detail}`,
      });
      // Refresh to ensure client displays actual backend state
      setRefreshTrigger((prev) => prev + 1);
    } finally {
      setActionInProgressId(null);
    }
  };

  const hasActiveFilters =
    Boolean(searchInput.trim()) ||
    Boolean(selectedCategory) ||
    Boolean(selectedStatus);

  const startOffset = items.length > 0 ? page * PAGE_SIZE + 1 : 0;
  const endOffset = items.length > 0 ? page * PAGE_SIZE + items.length : 0;

  return (
    <div className="app-layout">
      {/* Top Application Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand-group">
            <span className="brand-logo" aria-hidden="true">
              🛠️
            </span>
            <div>
              <h1 className="brand-title">Equipment Rental Desk</h1>
              <p className="brand-subtitle">
                KJBN Labs Community Tool Library Management
              </p>
            </div>
          </div>
          <div className="header-status">
            <span className="api-badge" title={`API endpoint: ${API_BASE_URL ?? "none"}`}>
              API: {API_BASE_URL ?? "local"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content" id="main-content">
        <section className="catalogue-section" aria-labelledby="catalogue-heading">
          {/* Section Header */}
          <div className="section-header">
            <div>
              <h2 id="catalogue-heading" className="section-title">
                Equipment Catalogue
              </h2>
              <p className="section-description">
                Search, inspect, and monitor library equipment availability and maintenance status.
              </p>
            </div>
            <div className="header-actions">
              <button
                type="button"
                className="btn btn-primary btn-add-item"
                onClick={handleOpenModal}
                aria-label="Add new equipment item"
              >
                <span aria-hidden="true">+</span> Add Item
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-refresh"
                onClick={handleRefresh}
                disabled={isFetching || actionInProgressId !== null}
                aria-label="Refresh catalogue items"
              >
                <span className={`refresh-icon ${isFetching ? "spinning" : ""}`} aria-hidden="true">
                  ↻
                </span>
                <span>{isFetching ? "Refreshing…" : "Refresh"}</span>
              </button>
            </div>
          </div>

          {/* Action Notification Banner */}
          {notification && (
            <div
              className={`notification-banner notification-${notification.type}`}
              role="alert"
              aria-live="polite"
            >
              <span className="notification-icon" aria-hidden="true">
                {notification.type === "success" ? "✓" : "⚠️"}
              </span>
              <span className="notification-message">{notification.message}</span>
              <button
                type="button"
                className="notification-close"
                onClick={() => setNotification(null)}
                aria-label="Dismiss notification"
              >
                ×
              </button>
            </div>
          )}

          {/* Search and Filters Toolbar */}
          <div className="filter-toolbar" role="search" aria-label="Filter equipment catalogue">
            <div className="search-field">
              <label htmlFor={searchInputId} className="field-label">
                Search Equipment
              </label>
              <div className="search-input-wrapper">
                <span className="search-icon" aria-hidden="true">
                  🔍
                </span>
                <input
                  id={searchInputId}
                  type="text"
                  className="input-text search-input"
                  placeholder="Search by item name or category…"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  autoComplete="off"
                />
                {searchInput && (
                  <button
                    type="button"
                    className="clear-search-btn"
                    onClick={() => setSearchInput("")}
                    aria-label="Clear search query"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>

            <div className="filter-field">
              <label htmlFor={categorySelectId} className="field-label">
                Category
              </label>
              <select
                id={categorySelectId}
                className="select-input"
                value={selectedCategory}
                onChange={handleCategoryChange}
              >
                <option value="">All Categories ({availableCategories.length})</option>
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-field">
              <label htmlFor={statusSelectId} className="field-label">
                Status
              </label>
              <select
                id={statusSelectId}
                className="select-input"
                value={selectedStatus}
                onChange={handleStatusChange}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {hasActiveFilters && (
              <div className="filter-actions">
                <button
                  type="button"
                  className="btn btn-subtle btn-reset"
                  onClick={handleResetFilters}
                  title="Clear all active filters"
                >
                  Clear Filters
                </button>
              </div>
            )}
          </div>

          {/* Results Summary Bar */}
          <div className="results-bar" aria-live="polite">
            <div className="results-count">
              {!initialLoading && !error && (
                <>
                  {items.length === 0 ? (
                    <span className="count-text">0 items found</span>
                  ) : (
                    <span className="count-text">
                      Showing <strong>{startOffset}–{endOffset}</strong> items
                      {page > 0 && <span className="muted"> (Page {page + 1})</span>}
                    </span>
                  )}
                </>
              )}
            </div>

            {isFetching && !initialLoading && (
              <span className="fetching-indicator" role="status">
                Updating results…
              </span>
            )}
          </div>

          {/* UI State 1: Initial Loading */}
          {initialLoading && (
            <div className="state-panel state-loading" role="status">
              <div className="spinner" aria-hidden="true" />
              <p className="state-title">Loading equipment catalogue…</p>
              <p className="state-subtitle muted">Connecting to rental desk service</p>
            </div>
          )}

          {/* UI State 2: Error Message */}
          {!initialLoading && error && (
            <div className="state-panel state-error" role="alert">
              <div className="error-icon" aria-hidden="true">
                ⚠️
              </div>
              <div className="error-content">
                <h3 className="error-title">
                  {error instanceof ApiClientError ? error.error : "Failed to load catalogue"}
                </h3>
                <p className="error-detail">
                  {error instanceof ApiClientError ? error.detail : error.message}
                </p>
                {error instanceof ApiClientError && (
                  <div className="error-meta">
                    <span className="error-code">Code: {error.code}</span>
                    {error.status > 0 && (
                      <span className="error-status">HTTP {error.status}</span>
                    )}
                  </div>
                )}
              </div>
              <button
                type="button"
                className="btn btn-primary btn-retry"
                onClick={handleRefresh}
              >
                Retry
              </button>
            </div>
          )}

          {/* UI State 3: Empty Catalogue (no items registered at all) */}
          {!initialLoading && !error && items.length === 0 && !hasActiveFilters && (
            <div className="state-panel state-empty">
              <div className="empty-icon" aria-hidden="true">
                📦
              </div>
              <h3 className="state-title">No equipment registered yet</h3>
              <p className="state-subtitle muted">
                The community equipment library currently has no catalogued items.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleOpenModal}
              >
                + Add First Equipment Item
              </button>
            </div>
          )}

          {/* UI State 4: No Search / Filter Matches */}
          {!initialLoading && !error && items.length === 0 && hasActiveFilters && (
            <div className="state-panel state-empty">
              <div className="empty-icon" aria-hidden="true">
                🔍
              </div>
              <h3 className="state-title">No matching equipment found</h3>
              <p className="state-subtitle muted">
                No items match your active search and filter criteria.
              </p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleResetFilters}
              >
                Clear All Filters
              </button>
            </div>
          )}

          {/* UI State 5: Catalogue Table Results with Maintenance Actions */}
          {!initialLoading && !error && items.length > 0 && (
            <div className="table-card">
              <div className="table-responsive">
                <table className="catalogue-table" aria-label="Equipment Catalogue Items">
                  <thead>
                    <tr>
                      <th scope="col" className="col-id">
                        ID
                      </th>
                      <th scope="col" className="col-name">
                        Equipment Name
                      </th>
                      <th scope="col" className="col-category">
                        Category
                      </th>
                      <th scope="col" className="col-status">
                        Status
                      </th>
                      <th scope="col" className="col-value text-right">
                        Replacement Value
                      </th>
                      <th scope="col" className="col-condition">
                        Condition Notes
                      </th>
                      <th scope="col" className="col-actions text-center">
                        Maintenance Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const maintenanceAction = isMaintenanceActionAllowed(item.status);
                      const isItemBusy = actionInProgressId === item.id;

                      return (
                        <tr key={item.id} className="item-row">
                          <td className="col-id font-mono">#{item.id}</td>
                          <td className="col-name">
                            <span className="item-name">{item.name}</span>
                          </td>
                          <td className="col-category">
                            <span className="category-pill">{item.category}</span>
                          </td>
                          <td className="col-status">
                            <span className={getStatusBadgeClass(item.status)}>
                              <span className="status-dot" aria-hidden="true" />
                              {getStatusLabel(item.status)}
                            </span>
                          </td>
                          <td className="col-value text-right font-mono">
                            {formatPaise(item.replacement_value)}
                          </td>
                          <td className="col-condition">
                            {item.condition_note ? (
                              <span className="condition-note" title={item.condition_note}>
                                {item.condition_note}
                              </span>
                            ) : (
                              <span className="condition-empty muted" aria-label="No notes recorded">
                                —
                              </span>
                            )}
                          </td>
                          <td className="col-actions text-center">
                            {maintenanceAction === "set_maintenance" && (
                              <button
                                type="button"
                                className="btn btn-sm btn-action-maintenance"
                                onClick={() => handleSetMaintenance(item)}
                                disabled={actionInProgressId !== null}
                                aria-label={`Mark item #${item.id} (${item.name}) as under maintenance`}
                              >
                                {isItemBusy ? "Updating…" : "Set Maintenance"}
                              </button>
                            )}

                            {maintenanceAction === "restore" && (
                              <button
                                type="button"
                                className="btn btn-sm btn-action-restore"
                                onClick={() => handleRestoreMaintenance(item)}
                                disabled={actionInProgressId !== null}
                                aria-label={`Restore item #${item.id} (${item.name}) to service`}
                              >
                                {isItemBusy ? "Restoring…" : "Restore Service"}
                              </button>
                            )}

                            {maintenanceAction === null && (
                              <span
                                className="action-inactive muted"
                                title="Item is currently reserved or checked out"
                              >
                                In Loan
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              <div className="pagination-bar" aria-label="Catalogue pagination">
                <div className="pagination-info muted">
                  Page <strong>{page + 1}</strong>
                </div>
                <div className="pagination-actions">
                  <button
                    type="button"
                    className="btn btn-secondary btn-pagination"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0 || isFetching || actionInProgressId !== null}
                    aria-label="Go to previous page"
                  >
                    ← Previous
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-pagination"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!hasNextPage || isFetching || actionInProgressId !== null}
                    aria-label="Go to next page"
                  >
                    Next →
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Add Item Modal Dialog */}
      {isAddModalOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !isSubmittingItem) {
              handleCloseModal();
            }
          }}
          aria-hidden={!isAddModalOpen}
        >
          <div
            className="modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-item-modal-title"
          >
            <div className="modal-header">
              <h3 id="add-item-modal-title" className="modal-title">
                Add New Equipment
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleCloseModal}
                disabled={isSubmittingItem}
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} noValidate>
              <div className="modal-body">
                {formApiError && (
                  <div className="form-alert-error" role="alert">
                    <span aria-hidden="true">⚠️</span>
                    <span>{formApiError}</span>
                  </div>
                )}

                {/* Item Name */}
                <div className="form-group">
                  <label htmlFor="item-form-name" className="field-label">
                    Equipment Name <span className="required-star">*</span>
                  </label>
                  <input
                    ref={nameInputRef}
                    id="item-form-name"
                    type="text"
                    className={`input-text ${formErrors.name ? "input-error" : ""}`}
                    placeholder="e.g. Cordless Drill 18V"
                    value={formValues.name}
                    onChange={(e) => handleFormFieldChange("name", e.target.value)}
                    disabled={isSubmittingItem}
                    maxLength={255}
                    required
                  />
                  {formErrors.name && (
                    <p className="field-error" role="alert">
                      {formErrors.name}
                    </p>
                  )}
                </div>

                {/* Category */}
                <div className="form-group">
                  <label htmlFor="item-form-category" className="field-label">
                    Category <span className="required-star">*</span>
                  </label>
                  <input
                    id="item-form-category"
                    type="text"
                    list="category-suggestions"
                    className={`input-text ${formErrors.category ? "input-error" : ""}`}
                    placeholder="e.g. Drills, Saws, Ladders"
                    value={formValues.category}
                    onChange={(e) => handleFormFieldChange("category", e.target.value)}
                    disabled={isSubmittingItem}
                    maxLength={100}
                    required
                  />
                  <datalist id="category-suggestions">
                    {availableCategories.map((cat) => (
                      <option key={cat} value={cat} />
                    ))}
                  </datalist>
                  {formErrors.category && (
                    <p className="field-error" role="alert">
                      {formErrors.category}
                    </p>
                  )}
                </div>

                {/* Replacement Value in Rupees */}
                <div className="form-group">
                  <label htmlFor="item-form-value" className="field-label">
                    Replacement Value (₹) <span className="required-star">*</span>
                  </label>
                  <div className="currency-input-wrapper">
                    <span className="currency-symbol" aria-hidden="true">
                      ₹
                    </span>
                    <input
                      id="item-form-value"
                      type="text"
                      inputMode="decimal"
                      className={`input-text currency-input ${formErrors.replacement_value ? "input-error" : ""}`}
                      placeholder="e.g. 4500 or 4500.00"
                      value={formValues.replacement_value}
                      onChange={(e) =>
                        handleFormFieldChange("replacement_value", e.target.value)
                      }
                      disabled={isSubmittingItem}
                      required
                    />
                  </div>
                  {formErrors.replacement_value ? (
                    <p className="field-error" role="alert">
                      {formErrors.replacement_value}
                    </p>
                  ) : (
                    <p className="field-hint muted">
                      Entered in Indian Rupees. Converted to integer paise for exact ledger accounting.
                    </p>
                  )}
                </div>

                {/* Condition Notes */}
                <div className="form-group">
                  <label htmlFor="item-form-note" className="field-label">
                    Condition Notes <span className="optional-tag">(Optional)</span>
                  </label>
                  <textarea
                    id="item-form-note"
                    className={`textarea-input ${formErrors.condition_note ? "input-error" : ""}`}
                    rows={3}
                    placeholder="e.g. Includes two 2Ah batteries and charger. Serial #D-1029."
                    value={formValues.condition_note}
                    onChange={(e) =>
                      handleFormFieldChange("condition_note", e.target.value)
                    }
                    disabled={isSubmittingItem}
                    maxLength={2000}
                  />
                  {formErrors.condition_note && (
                    <p className="field-error" role="alert">
                      {formErrors.condition_note}
                    </p>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCloseModal}
                  disabled={isSubmittingItem}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-submit-item"
                  disabled={isSubmittingItem}
                >
                  {isSubmittingItem ? (
                    <>
                      <span className="spinner-sm" aria-hidden="true" />
                      <span>Creating Item…</span>
                    </>
                  ) : (
                    "Create Equipment Item"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-container">
          <p className="muted">
            Equipment Rental Desk · Internal Management Interface · Problem 1 (KJBN Labs)
          </p>
        </div>
      </footer>
    </div>
  );
}
