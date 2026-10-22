import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ApiClientError,
  API_BASE_URL,
  cancelLoan,
  checkoutLoan,
  createItem,
  createMember,
  deleteMember,
  fetchItems,
  fetchLoans,
  fetchMembers,
  fetchOverdueLoans,
  getMemberStatement,
  recordPayment,
  reinstateMember,
  reserveLoan,
  restoreItemMaintenance,
  returnLoan,
  setItemMaintenance,
  suspendMember,
} from "./api/client";
import type {
  ItemCreate,
  ItemListParams,
  ItemResponse,
  ItemStatus,
  LoanListParams,
  LoanResponse,
  LoanStatus,
  MemberCreate,
  MemberListParams,
  MemberResponse,
  MemberStatementResponse,
  MemberStatus,
  OverdueLoansParams,
} from "./api/types";
import {
  formatPaise,
  formatUtcToIst,
  isLoanActionAllowed,
  isMaintenanceActionAllowed,
  type ItemFormValues,
  type MemberFormValues,
  type PaymentFormValues,
  type ReservationFormValues,
  validateItemForm,
  validateMemberForm,
  validatePaymentForm,
  validateReservationForm,
} from "./api/utils";

const PAGE_SIZE = 10;

const LOAN_STATUS_OPTIONS: { value: LoanStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "RESERVED", label: "Reserved" },
  { value: "CHECKED_OUT", label: "Checked Out" },
  { value: "RETURNED", label: "Returned" },
  { value: "CANCELLED", label: "Cancelled" },
];

const ITEM_STATUS_OPTIONS: { value: ItemStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "AVAILABLE", label: "Available" },
  { value: "RESERVED", label: "Reserved" },
  { value: "CHECKED_OUT", label: "Checked Out" },
  { value: "UNDER_MAINTENANCE", label: "Under Maintenance" },
];

const MEMBER_STATUS_OPTIONS: { value: MemberStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "ACTIVE", label: "Active" },
  { value: "SUSPENDED", label: "Suspended" },
];

function getItemStatusBadgeClass(status: ItemStatus): string {
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

function getItemStatusLabel(status: ItemStatus): string {
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

function getMemberStatusBadgeClass(status: MemberStatus): string {
  switch (status) {
    case "ACTIVE":
      return "status-badge status-available";
    case "SUSPENDED":
      return "status-badge status-suspended";
    default:
      return "status-badge";
  }
}

function getMemberStatusLabel(status: MemberStatus): string {
  switch (status) {
    case "ACTIVE":
      return "Active";
    case "SUSPENDED":
      return "Suspended";
    default:
      return status;
  }
}

function getLoanStatusBadgeClass(status: LoanStatus, isOverdue = false): string {
  if (isOverdue && status === "CHECKED_OUT") {
    return "status-badge status-overdue";
  }
  switch (status) {
    case "RESERVED":
      return "status-badge status-reserved";
    case "CHECKED_OUT":
      return "status-badge status-checked-out";
    case "RETURNED":
      return "status-badge status-available";
    case "CANCELLED":
      return "status-badge status-under-maintenance";
    default:
      return "status-badge";
  }
}

function getLoanStatusLabel(status: LoanStatus, isOverdue = false): string {
  if (isOverdue && status === "CHECKED_OUT") {
    return "Overdue";
  }
  switch (status) {
    case "RESERVED":
      return "Reserved";
    case "CHECKED_OUT":
      return "Checked Out";
    case "RETURNED":
      return "Returned";
    case "CANCELLED":
      return "Cancelled";
    default:
      return status;
  }
}

interface NotificationState {
  type: "success" | "error";
  message: string;
}

export default function App() {
  // Navigation tab state
  const [activeTab, setActiveTab] = useState<"catalogue" | "members" | "loans">("catalogue");

  // Global notification banner (success / action error)
  const [notification, setNotification] = useState<NotificationState | null>(null);

  // ============================================================================
  // Item Catalogue State
  // ============================================================================
  const searchInputId = useId();
  const categorySelectId = useId();
  const itemStatusSelectId = useId();

  const [searchInput, setSearchInput] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedItemStatus, setSelectedItemStatus] = useState<ItemStatus | "">("");

  const [itemPage, setItemPage] = useState<number>(0);
  const [items, setItems] = useState<ItemResponse[]>([]);
  const [hasNextItemPage, setHasNextItemPage] = useState<boolean>(false);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);

  const [initialItemsLoading, setInitialItemsLoading] = useState<boolean>(true);
  const [isFetchingItems, setIsFetchingItems] = useState<boolean>(false);
  const [itemRefreshTrigger, setItemRefreshTrigger] = useState<number>(0);
  const [itemsError, setItemsError] = useState<ApiClientError | Error | null>(null);

  const [itemActionInProgressId, setItemActionInProgressId] = useState<number | null>(null);

  // Add Item Modal state
  const [isAddItemModalOpen, setIsAddItemModalOpen] = useState<boolean>(false);
  const [itemFormValues, setItemFormValues] = useState<ItemFormValues>({
    name: "",
    category: "",
    replacement_value: "",
    condition_note: "",
  });
  const [itemFormErrors, setItemFormErrors] = useState<Record<string, string>>({});
  const [isSubmittingItem, setIsSubmittingItem] = useState<boolean>(false);
  const [itemFormApiError, setItemFormApiError] = useState<string | null>(null);
  const itemNameInputRef = useRef<HTMLInputElement>(null);

  // ============================================================================
  // Member Management State
  // ============================================================================
  const memberStatusSelectId = useId();

  const [selectedMemberStatus, setSelectedMemberStatus] = useState<MemberStatus | "">("");
  const [memberPage, setMemberPage] = useState<number>(0);
  const [members, setMembers] = useState<MemberResponse[]>([]);
  const [hasNextMemberPage, setHasNextMemberPage] = useState<boolean>(false);

  const [initialMembersLoading, setInitialMembersLoading] = useState<boolean>(true);
  const [isFetchingMembers, setIsFetchingMembers] = useState<boolean>(false);
  const [memberRefreshTrigger, setMemberRefreshTrigger] = useState<number>(0);
  const [membersError, setMembersError] = useState<ApiClientError | Error | null>(null);

  const [memberActionInProgressId, setMemberActionInProgressId] = useState<number | null>(null);

  // Add Member Modal state
  const [isAddMemberModalOpen, setIsAddMemberModalOpen] = useState<boolean>(false);
  const [memberFormValues, setMemberFormValues] = useState<MemberFormValues>({
    name: "",
    phone: "",
  });
  const [memberFormErrors, setMemberFormErrors] = useState<Record<string, string>>({});
  const [isSubmittingMember, setIsSubmittingMember] = useState<boolean>(false);
  const [memberFormApiError, setMemberFormApiError] = useState<string | null>(null);
  const memberNameInputRef = useRef<HTMLInputElement>(null);

  // ============================================================================
  // Member Statement & Fee Payment State
  // ============================================================================
  const [selectedStatementMember, setSelectedStatementMember] = useState<MemberResponse | null>(null);
  const [statementData, setStatementData] = useState<MemberStatementResponse | null>(null);
  const [isStatementLoading, setIsStatementLoading] = useState<boolean>(false);
  const [statementError, setStatementError] = useState<ApiClientError | Error | null>(null);
  const [activeStatementTab, setActiveStatementTab] = useState<"loans" | "payments">("loans");

  // Payment form state inside statement modal
  const [isPaymentFormOpen, setIsPaymentFormOpen] = useState<boolean>(false);
  const [paymentFormValues, setPaymentFormValues] = useState<PaymentFormValues>({
    amount: "",
    note: "",
  });
  const [paymentFormErrors, setPaymentFormErrors] = useState<Record<string, string>>({});
  const [isSubmittingPayment, setIsSubmittingPayment] = useState<boolean>(false);
  const [paymentFormApiError, setPaymentFormApiError] = useState<string | null>(null);
  const paymentAmountInputRef = useRef<HTMLInputElement>(null);

  // ============================================================================
  // Loan Management State
  // ============================================================================
  const loanStatusSelectId = useId();
  const loanMemberIdInputId = useId();
  const loanItemIdInputId = useId();

  const [loanViewMode, setLoanViewMode] = useState<"all" | "overdue">("all");
  const [selectedLoanStatus, setSelectedLoanStatus] = useState<LoanStatus | "">("");
  const [loanMemberIdFilter, setLoanMemberIdFilter] = useState<string>("");
  const [loanItemIdFilter, setLoanItemIdFilter] = useState<string>("");
  const [debouncedLoanMemberId, setDebouncedLoanMemberId] = useState<string>("");
  const [debouncedLoanItemId, setDebouncedLoanItemId] = useState<string>("");

  const [loanPage, setLoanPage] = useState<number>(0);
  const [loans, setLoans] = useState<LoanResponse[]>([]);
  const [hasNextLoanPage, setHasNextLoanPage] = useState<boolean>(false);

  const [initialLoansLoading, setInitialLoansLoading] = useState<boolean>(true);
  const [isFetchingLoans, setIsFetchingLoans] = useState<boolean>(false);
  const [loanRefreshTrigger, setLoanRefreshTrigger] = useState<number>(0);
  const [loansError, setLoansError] = useState<ApiClientError | Error | null>(null);

  const [loanActionInProgressId, setLoanActionInProgressId] = useState<number | null>(null);

  // Reserve Equipment Modal state
  const [isReserveModalOpen, setIsReserveModalOpen] = useState<boolean>(false);
  const [reserveFormValues, setReserveFormValues] = useState<ReservationFormValues>({
    member_id: "",
    item_id: "",
  });
  const [reserveFormErrors, setReserveFormErrors] = useState<Record<string, string>>({});
  const [isSubmittingReserve, setIsSubmittingReserve] = useState<boolean>(false);
  const [reserveFormApiError, setReserveFormApiError] = useState<string | null>(null);

  // Options for reservation select dropdowns
  const [availableItemsForReserve, setAvailableItemsForReserve] = useState<ItemResponse[]>([]);
  const [activeMembersForReserve, setActiveMembersForReserve] = useState<MemberResponse[]>([]);
  const [isLoadingReserveOptions, setIsLoadingReserveOptions] = useState<boolean>(false);
  const reserveOptionsAbortControllerRef = useRef<AbortController | null>(null);

  // Reserve Equipment Modal close helper
  const handleCloseReserveModal = useCallback(() => {
    if (isSubmittingReserve) return;
    if (reserveOptionsAbortControllerRef.current) {
      reserveOptionsAbortControllerRef.current.abort();
      reserveOptionsAbortControllerRef.current = null;
    }
    setIsReserveModalOpen(false);
    setReserveFormErrors({});
    setReserveFormApiError(null);
    setActiveMembersForReserve([]);
    setAvailableItemsForReserve([]);
    setIsLoadingReserveOptions(false);
  }, [isSubmittingReserve]);

  // Close statement modal helper
  const handleCloseStatement = useCallback(() => {
    if (isSubmittingPayment) return;
    setSelectedStatementMember(null);
    setStatementData(null);
    setStatementError(null);
    setIsPaymentFormOpen(false);
    setPaymentFormValues({ amount: "", note: "" });
    setPaymentFormErrors({});
    setPaymentFormApiError(null);
  }, [isSubmittingPayment]);

  // ============================================================================
  // Effects & Lifecycles
  // ============================================================================

  // Cleanup in-flight reserve options request on unmount
  useEffect(() => {
    return () => {
      if (reserveOptionsAbortControllerRef.current) {
        reserveOptionsAbortControllerRef.current.abort();
      }
    };
  }, []);

  // Auto-focus Item Name input when modal opens
  useEffect(() => {
    if (isAddItemModalOpen) {
      const timer = setTimeout(() => {
        itemNameInputRef.current?.focus();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [isAddItemModalOpen]);

  // Auto-focus Member Name input when modal opens
  useEffect(() => {
    if (isAddMemberModalOpen) {
      const timer = setTimeout(() => {
        memberNameInputRef.current?.focus();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [isAddMemberModalOpen]);

  // Auto-focus Payment Amount input when payment form expands
  useEffect(() => {
    if (isPaymentFormOpen) {
      const timer = setTimeout(() => {
        paymentAmountInputRef.current?.focus();
      }, 60);
      return () => clearTimeout(timer);
    }
  }, [isPaymentFormOpen]);

  // Global Escape key handler for open modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (selectedStatementMember && !isSubmittingPayment) {
          if (isPaymentFormOpen) {
            setIsPaymentFormOpen(false);
          } else {
            handleCloseStatement();
          }
        } else if (isAddItemModalOpen && !isSubmittingItem) {
          handleCloseAddItemModal();
        } else if (isAddMemberModalOpen && !isSubmittingMember) {
          handleCloseAddMemberModal();
        } else if (isReserveModalOpen && !isSubmittingReserve) {
          handleCloseReserveModal();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isAddItemModalOpen,
    isSubmittingItem,
    isAddMemberModalOpen,
    isSubmittingMember,
    selectedStatementMember,
    isPaymentFormOpen,
    isSubmittingPayment,
    handleCloseStatement,
    isReserveModalOpen,
    isSubmittingReserve,
    handleCloseReserveModal,
  ]);

  // Debounce member ID filter for loans
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedLoanMemberId(loanMemberIdFilter.trim());
      setLoanPage(0);
    }, 300);
    return () => clearTimeout(handler);
  }, [loanMemberIdFilter]);

  // Debounce item ID filter for loans
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedLoanItemId(loanItemIdFilter.trim());
      setLoanPage(0);
    }, 300);
    return () => clearTimeout(handler);
  }, [loanItemIdFilter]);

  // Load loans or overdue loans with pagination and filters
  useEffect(() => {
    const controller = new AbortController();
    let isCancelled = false;

    async function loadLoans() {
      setIsFetchingLoans(true);
      setLoansError(null);

      const parsedMemberId = debouncedLoanMemberId
        ? parseInt(debouncedLoanMemberId, 10)
        : undefined;
      const validMemberId =
        parsedMemberId !== undefined && !Number.isNaN(parsedMemberId) && parsedMemberId > 0
          ? parsedMemberId
          : undefined;

      const parsedItemId = debouncedLoanItemId
        ? parseInt(debouncedLoanItemId, 10)
        : undefined;
      const validItemId =
        parsedItemId !== undefined && !Number.isNaN(parsedItemId) && parsedItemId > 0
          ? parsedItemId
          : undefined;

      try {
        let result: LoanResponse[];
        if (loanViewMode === "overdue") {
          const overdueParams: OverdueLoansParams = {
            limit: PAGE_SIZE + 1,
            offset: loanPage * PAGE_SIZE,
            member_id: validMemberId,
            item_id: validItemId,
          };
          result = await fetchOverdueLoans(overdueParams, { signal: controller.signal });
        } else {
          const params: LoanListParams = {
            limit: PAGE_SIZE + 1,
            offset: loanPage * PAGE_SIZE,
            status: selectedLoanStatus || undefined,
            member_id: validMemberId,
            item_id: validItemId,
          };
          result = await fetchLoans(params, { signal: controller.signal });
        }

        if (!isCancelled) {
          if (result.length > PAGE_SIZE) {
            setLoans(result.slice(0, PAGE_SIZE));
            setHasNextLoanPage(true);
          } else {
            setLoans(result);
            setHasNextLoanPage(false);
          }
        }
      } catch (err) {
        if (isCancelled || (err instanceof Error && err.name === "AbortError")) {
          return;
        }
        if (!isCancelled) {
          setLoansError(err instanceof Error ? err : new Error(String(err)));
          setLoans([]);
          setHasNextLoanPage(false);
        }
      } finally {
        if (!isCancelled) {
          setIsFetchingLoans(false);
          setInitialLoansLoading(false);
        }
      }
    }

    loadLoans();

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [
    loanViewMode,
    loanPage,
    selectedLoanStatus,
    debouncedLoanMemberId,
    debouncedLoanItemId,
    loanRefreshTrigger,
  ]);

  // Auto-dismiss notification after 6 seconds
  useEffect(() => {
    if (!notification) return;
    const timer = setTimeout(() => {
      setNotification(null);
    }, 6000);
    return () => clearTimeout(timer);
  }, [notification]);

  // Debounce search query input (300ms) for items
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
      setItemPage(0);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchInput]);

  // Refresh handlers
  const handleRefreshItems = useCallback(() => {
    if (isFetchingItems) return;
    setItemRefreshTrigger((prev) => prev + 1);
  }, [isFetchingItems]);

  const handleRefreshMembers = useCallback(() => {
    if (isFetchingMembers) return;
    setMemberRefreshTrigger((prev) => prev + 1);
  }, [isFetchingMembers]);

  // Load available item categories on initial mount and when explicitly refreshed
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
      });

    return () => controller.abort();
  }, [itemRefreshTrigger]);

  // Fetch paginated items
  useEffect(() => {
    const controller = new AbortController();
    setIsFetchingItems(true);
    setItemsError(null);

    const params: ItemListParams = {
      limit: PAGE_SIZE + 1,
      offset: itemPage * PAGE_SIZE,
    };

    if (debouncedQuery) {
      params.q = debouncedQuery;
    }
    if (selectedCategory) {
      params.category = selectedCategory;
    }
    if (selectedItemStatus) {
      params.status = selectedItemStatus;
    }

    fetchItems(params, { signal: controller.signal })
      .then((fetchedItems) => {
        if (controller.signal.aborted) return;

        if (fetchedItems.length > PAGE_SIZE) {
          setHasNextItemPage(true);
          setItems(fetchedItems.slice(0, PAGE_SIZE));
        } else {
          setHasNextItemPage(false);
          setItems(fetchedItems);
        }

        // Dynamically incorporate newly discovered categories
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

        setInitialItemsLoading(false);
        setIsFetchingItems(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
          return;
        }
        setItemsError(err instanceof Error ? err : new Error(String(err)));
        setInitialItemsLoading(false);
        setIsFetchingItems(false);
      });

    return () => controller.abort();
  }, [debouncedQuery, selectedCategory, selectedItemStatus, itemPage, itemRefreshTrigger]);

  // Fetch paginated members
  useEffect(() => {
    const controller = new AbortController();
    setIsFetchingMembers(true);
    setMembersError(null);

    const params: MemberListParams = {
      limit: PAGE_SIZE + 1,
      offset: memberPage * PAGE_SIZE,
    };

    if (selectedMemberStatus) {
      params.status = selectedMemberStatus;
    }

    fetchMembers(params, { signal: controller.signal })
      .then((fetchedMembers) => {
        if (controller.signal.aborted) return;

        if (fetchedMembers.length > PAGE_SIZE) {
          setHasNextMemberPage(true);
          setMembers(fetchedMembers.slice(0, PAGE_SIZE));
        } else {
          setHasNextMemberPage(false);
          setMembers(fetchedMembers);
        }

        setInitialMembersLoading(false);
        setIsFetchingMembers(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
          return;
        }
        setMembersError(err instanceof Error ? err : new Error(String(err)));
        setInitialMembersLoading(false);
        setIsFetchingMembers(false);
      });

    return () => controller.abort();
  }, [selectedMemberStatus, memberPage, memberRefreshTrigger]);

  // ============================================================================
  // Item Handlers
  // ============================================================================

  const handleOpenAddItemModal = () => {
    setItemFormValues({ name: "", category: "", replacement_value: "", condition_note: "" });
    setItemFormErrors({});
    setItemFormApiError(null);
    setIsAddItemModalOpen(true);
  };

  const handleCloseAddItemModal = () => {
    if (isSubmittingItem) return;
    setIsAddItemModalOpen(false);
    setItemFormErrors({});
    setItemFormApiError(null);
  };

  const handleItemFormFieldChange = (field: keyof ItemFormValues, value: string) => {
    setItemFormValues((prev) => ({ ...prev, [field]: value }));
    if (itemFormErrors[field]) {
      setItemFormErrors((prev) => {
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    }
    if (itemFormApiError) {
      setItemFormApiError(null);
    }
  };

  const handleCreateItemSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setItemFormApiError(null);

    const validation = validateItemForm(itemFormValues);
    if (!validation.isValid || validation.parsedPaise === undefined) {
      setItemFormErrors(validation.errors);
      return;
    }

    setItemFormErrors({});
    setIsSubmittingItem(true);

    try {
      const payload: ItemCreate = {
        name: itemFormValues.name.trim(),
        category: itemFormValues.category.trim(),
        replacement_value: validation.parsedPaise,
        condition_note: itemFormValues.condition_note?.trim() || null,
      };

      const newItem = await createItem(payload);
      handleCloseAddItemModal();
      setNotification({
        type: "success",
        message: `Successfully created equipment item "${newItem.name}" (#${newItem.id}) in Available status.`,
      });
      setItemRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setItemFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setItemFormApiError(err.message);
      } else {
        setItemFormApiError("An unexpected error occurred while creating the equipment item.");
      }
    } finally {
      setIsSubmittingItem(false);
    }
  };

  const handleSetMaintenance = async (item: ItemResponse) => {
    if (itemActionInProgressId !== null) return;
    setItemActionInProgressId(item.id);

    try {
      const updated = await setItemMaintenance(item.id);
      setNotification({
        type: "success",
        message: `Item #${updated.id} ("${updated.name}") has been marked as Under Maintenance.`,
      });
      setItemRefreshTrigger((prev) => prev + 1);
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
      setItemRefreshTrigger((prev) => prev + 1);
    } finally {
      setItemActionInProgressId(null);
    }
  };

  const handleRestoreMaintenance = async (item: ItemResponse) => {
    if (itemActionInProgressId !== null) return;
    setItemActionInProgressId(item.id);

    try {
      const updated = await restoreItemMaintenance(item.id);
      setNotification({
        type: "success",
        message: `Item #${updated.id} ("${updated.name}") has been restored to service (${getItemStatusLabel(updated.status)}).`,
      });
      setItemRefreshTrigger((prev) => prev + 1);
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
      setItemRefreshTrigger((prev) => prev + 1);
    } finally {
      setItemActionInProgressId(null);
    }
  };

  // ============================================================================
  // Member Handlers
  // ============================================================================

  const handleOpenAddMemberModal = () => {
    setMemberFormValues({ name: "", phone: "" });
    setMemberFormErrors({});
    setMemberFormApiError(null);
    setIsAddMemberModalOpen(true);
  };

  const handleCloseAddMemberModal = () => {
    if (isSubmittingMember) return;
    setIsAddMemberModalOpen(false);
    setMemberFormErrors({});
    setMemberFormApiError(null);
  };

  const handleMemberFormFieldChange = (field: keyof MemberFormValues, value: string) => {
    setMemberFormValues((prev) => ({ ...prev, [field]: value }));
    if (memberFormErrors[field]) {
      setMemberFormErrors((prev) => {
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    }
    if (memberFormApiError) {
      setMemberFormApiError(null);
    }
  };

  const handleCreateMemberSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMemberFormApiError(null);

    const validation = validateMemberForm(memberFormValues);
    if (!validation.isValid) {
      setMemberFormErrors(validation.errors);
      return;
    }

    setMemberFormErrors({});
    setIsSubmittingMember(true);

    try {
      const payload: MemberCreate = {
        name: memberFormValues.name.trim(),
        phone: memberFormValues.phone.trim(),
      };

      const newMember = await createMember(payload);
      handleCloseAddMemberModal();
      setNotification({
        type: "success",
        message: `Successfully registered member "${newMember.name}" (#${newMember.id}).`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setMemberFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setMemberFormApiError(err.message);
      } else {
        setMemberFormApiError("An unexpected error occurred while registering the member.");
      }
    } finally {
      setIsSubmittingMember(false);
    }
  };

  const handleSuspendMember = async (member: MemberResponse) => {
    if (memberActionInProgressId !== null) return;
    if (!window.confirm(`Are you sure you want to suspend member ${member.name} (#${member.id})? This will block their borrowing eligibility.`)) {
      return;
    }

    setMemberActionInProgressId(member.id);
    try {
      const updated = await suspendMember(member.id);
      setNotification({
        type: "success",
        message: `Member #${updated.id} ("${updated.name}") has been suspended.`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const detail =
        err instanceof ApiClientError
          ? `${err.error}: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to suspend member.";
      setNotification({
        type: "error",
        message: `Failed to suspend member #${member.id}. ${detail}`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } finally {
      setMemberActionInProgressId(null);
    }
  };

  const handleReinstateMember = async (member: MemberResponse) => {
    if (memberActionInProgressId !== null) return;
    if (!window.confirm(`Are you sure you want to reinstate member ${member.name} (#${member.id}) to Active status?`)) {
      return;
    }

    setMemberActionInProgressId(member.id);
    try {
      const updated = await reinstateMember(member.id);
      setNotification({
        type: "success",
        message: `Member #${updated.id} ("${updated.name}") has been reinstated to Active status.`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const detail =
        err instanceof ApiClientError
          ? `${err.error}: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to reinstate member.";
      setNotification({
        type: "error",
        message: `Failed to reinstate member #${member.id}. ${detail}`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } finally {
      setMemberActionInProgressId(null);
    }
  };

  const handleDeleteMember = async (member: MemberResponse) => {
    if (memberActionInProgressId !== null) return;
    if (
      !window.confirm(
        `Are you sure you want to delete member ${member.name} (#${member.id})?\n\nNote: Members with active or historical loans, payments, or fee balances cannot be deleted.`
      )
    ) {
      return;
    }

    setMemberActionInProgressId(member.id);
    try {
      await deleteMember(member.id);
      setNotification({
        type: "success",
        message: `Member #${member.id} ("${member.name}") was successfully deleted.`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err: unknown) {
      const detail =
        err instanceof ApiClientError
          ? `${err.error}: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to delete member.";
      setNotification({
        type: "error",
        message: `Could not delete member #${member.id}. ${detail}`,
      });
      setMemberRefreshTrigger((prev) => prev + 1);
    } finally {
      setMemberActionInProgressId(null);
    }
  };

  // ============================================================================
  // Member Statement & Fee Payment Handlers
  // ============================================================================

  // Open statement modal and fetch statement ledger
  const handleOpenStatement = useCallback(async (member: MemberResponse) => {
    setSelectedStatementMember(member);
    setStatementData(null);
    setIsStatementLoading(true);
    setStatementError(null);
    setIsPaymentFormOpen(false);
    setPaymentFormValues({ amount: "", note: "" });
    setPaymentFormErrors({});
    setPaymentFormApiError(null);
    setActiveStatementTab("loans");

    try {
      const data = await getMemberStatement(member.id);
      setStatementData(data);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setStatementError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsStatementLoading(false);
    }
  }, []);

  // Refresh statement data
  const handleRefreshStatement = useCallback(async () => {
    if (!selectedStatementMember) return;
    setIsStatementLoading(true);
    setStatementError(null);
    try {
      const data = await getMemberStatement(selectedStatementMember.id);
      setStatementData(data);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setStatementError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsStatementLoading(false);
    }
  }, [selectedStatementMember]);

  // Payment form field change handler
  const handlePaymentFormFieldChange = (field: keyof PaymentFormValues, val: string) => {
    setPaymentFormValues((prev) => ({ ...prev, [field]: val }));
    if (paymentFormErrors[field]) {
      setPaymentFormErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
    if (paymentFormApiError) {
      setPaymentFormApiError(null);
    }
  };

  // Quick action: populate full outstanding balance into payment input
  const handlePayFullBalance = () => {
    const currentBalance =
      statementData?.current_outstanding_balance ?? selectedStatementMember?.running_fee_balance ?? 0;
    if (currentBalance > 0) {
      const rupees = (currentBalance / 100).toFixed(2);
      handlePaymentFormFieldChange("amount", rupees);
    }
  };

  // Submit payment to backend
  const handleRecordPaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStatementMember || isSubmittingPayment) return;

    const currentBalance =
      statementData?.current_outstanding_balance ?? selectedStatementMember.running_fee_balance;
    const validation = validatePaymentForm(paymentFormValues, currentBalance);
    if (!validation.isValid || validation.parsedPaise === undefined) {
      setPaymentFormErrors(validation.errors);
      return;
    }

    setIsSubmittingPayment(true);
    setPaymentFormApiError(null);

    try {
      const paymentResponse = await recordPayment(selectedStatementMember.id, {
        amount_paise: validation.parsedPaise,
        note: paymentFormValues.note ? paymentFormValues.note.trim() : null,
      });

      // Show success notification
      setNotification({
        type: "success",
        message: `Payment of ${formatPaise(paymentResponse.amount)} recorded for ${selectedStatementMember.name}.`,
      });

      // Reset payment form
      setPaymentFormValues({ amount: "", note: "" });
      setPaymentFormErrors({});
      setIsPaymentFormOpen(false);

      // Refresh statement data from server
      const refreshedStatement = await getMemberStatement(selectedStatementMember.id);
      setStatementData(refreshedStatement);

      // Update balance in local member list & selected member
      setMembers((prev) =>
        prev.map((m) =>
          m.id === selectedStatementMember.id
            ? { ...m, running_fee_balance: refreshedStatement.current_outstanding_balance }
            : m,
        ),
      );
      setSelectedStatementMember((prev) =>
        prev
          ? { ...prev, running_fee_balance: refreshedStatement.current_outstanding_balance }
          : null,
      );

      // Trigger member directory refresh using the existing mechanism
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setPaymentFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setPaymentFormApiError(err.message);
      } else {
        setPaymentFormApiError("Failed to record fee payment. Please check network connection.");
      }
    } finally {
      setIsSubmittingPayment(false);
    }
  };

  // ============================================================================
  // Loan Reservation & Checkout Handlers
  // ============================================================================

  // Load active members and available items for reservation modal with error handling and retry support
  const loadReserveOptions = useCallback(async () => {
    if (reserveOptionsAbortControllerRef.current) {
      reserveOptionsAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    reserveOptionsAbortControllerRef.current = controller;

    setIsLoadingReserveOptions(true);
    setReserveFormApiError(null);
    // Ensure failed request does not leave stale member or item options from a previous attempt
    setActiveMembersForReserve([]);
    setAvailableItemsForReserve([]);

    try {
      const [membersRes, itemsRes] = await Promise.all([
        fetchMembers({ status: "ACTIVE", limit: 500 }, { signal: controller.signal }),
        fetchItems({ status: "AVAILABLE", limit: 500 }, { signal: controller.signal }),
      ]);
      if (!controller.signal.aborted) {
        setActiveMembersForReserve(membersRes);
        setAvailableItemsForReserve(itemsRes);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
        return;
      }
      setActiveMembersForReserve([]);
      setAvailableItemsForReserve([]);
      if (err instanceof ApiClientError) {
        setReserveFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setReserveFormApiError(err.message);
      } else {
        setReserveFormApiError(
          "Failed to load reservation options. Please check network connection.",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingReserveOptions(false);
      }
    }
  }, []);

  // Open Reserve Equipment Modal and load real active members and available items
  const handleOpenReserveModal = () => {
    setIsReserveModalOpen(true);
    setReserveFormValues({ member_id: "", item_id: "" });
    setReserveFormErrors({});
    loadReserveOptions();
  };

  // Submit equipment reservation form
  const handleReserveFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmittingReserve) return;

    const validation = validateReservationForm(reserveFormValues);
    if (
      !validation.isValid ||
      validation.parsedMemberId === undefined ||
      validation.parsedItemId === undefined
    ) {
      setReserveFormErrors(validation.errors);
      return;
    }

    setIsSubmittingReserve(true);
    setReserveFormApiError(null);

    try {
      const newLoan = await reserveLoan({
        member_id: validation.parsedMemberId,
        item_id: validation.parsedItemId,
      });

      setNotification({
        type: "success",
        message: `Equipment reserved successfully (Loan #${newLoan.id}). Held for 48 hours.`,
      });

      handleCloseReserveModal();
      setLoanRefreshTrigger((prev) => prev + 1);
      setItemRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setReserveFormApiError(`${err.error}: ${err.detail}`);
      } else if (err instanceof Error) {
        setReserveFormApiError(err.message);
      } else {
        setReserveFormApiError("Failed to reserve equipment. Please check network connection.");
      }
    } finally {
      setIsSubmittingReserve(false);
    }
  };

  // Check out a reserved loan
  const handleCheckoutLoan = async (loan: LoanResponse) => {
    if (loan.status !== "RESERVED" || loanActionInProgressId !== null) return;

    const confirmed = window.confirm(
      `Check out equipment for Loan #${loan.id} (Member #${loan.member_id}, Item #${loan.item_id})?\n\nThis begins the 7-day loan period.`,
    );
    if (!confirmed) return;

    setLoanActionInProgressId(loan.id);

    try {
      const updatedLoan = await checkoutLoan(loan.id);
      setNotification({
        type: "success",
        message: `Loan #${updatedLoan.id} checked out successfully. Return due by ${formatUtcToIst(
          updatedLoan.due_at,
        )}.`,
      });
      setLoanRefreshTrigger((prev) => prev + 1);
      setItemRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      let detail = "Check-out request failed.";
      if (err instanceof ApiClientError) {
        detail = `${err.error}: ${err.detail}`;
      } else if (err instanceof Error) {
        detail = err.message;
      }
      setNotification({
        type: "error",
        message: `Could not check out Loan #${loan.id}. ${detail}`,
      });
      setLoanRefreshTrigger((prev) => prev + 1);
    } finally {
      setLoanActionInProgressId(null);
    }
  };

  // Return a checked-out loan (with backend late fee assessment)
  const handleReturnLoan = async (loan: LoanResponse) => {
    if (loan.status !== "CHECKED_OUT" || loanActionInProgressId !== null) return;

    const isOverdue =
      loanViewMode === "overdue" ||
      (loan.due_at !== null && new Date(loan.due_at).getTime() < Date.now());

    const confirmMsg = isOverdue
      ? `Return overdue equipment for Loan #${loan.id} (Member #${loan.member_id}, Item #${loan.item_id})?\n\nThis will record the return timestamp, calculate late fees according to rental desk rules (₹10/day, capped at ₹200 and replacement value), add the fee to Member #${loan.member_id}'s account balance, and restore the item to Available.`
      : `Return equipment for Loan #${loan.id} (Member #${loan.member_id}, Item #${loan.item_id})?\n\nThis will record the return timestamp and restore the equipment item to Available.`;

    const confirmed = window.confirm(confirmMsg);
    if (!confirmed) return;

    setLoanActionInProgressId(loan.id);

    try {
      const updatedLoan = await returnLoan(loan.id);
      const feeDetail =
        updatedLoan.fee_charged > 0
          ? ` Late fee of ${formatPaise(
              updatedLoan.fee_charged,
            )} was assessed and added to Member #${loan.member_id}'s balance.`
          : " Returned on time with zero late fees.";

      setNotification({
        type: "success",
        message: `Equipment for Loan #${updatedLoan.id} returned successfully.${feeDetail}`,
      });

      // Refresh loans list, equipment catalogue, and member balances
      setLoanRefreshTrigger((prev) => prev + 1);
      setItemRefreshTrigger((prev) => prev + 1);
      setMemberRefreshTrigger((prev) => prev + 1);

      // If active statement member is open for this member, refresh statement
      if (selectedStatementMember && selectedStatementMember.id === loan.member_id) {
        handleRefreshStatement();
      }
    } catch (err) {
      let detail = "Return request failed.";
      if (err instanceof ApiClientError) {
        detail = `[${err.code}] ${err.detail || err.error}`;
      } else if (err instanceof Error) {
        detail = err.message;
      }
      setNotification({
        type: "error",
        message: `Could not return Loan #${loan.id}. ${detail}`,
      });
      setLoanRefreshTrigger((prev) => prev + 1);
    } finally {
      setLoanActionInProgressId(null);
    }
  };

  // Cancel a reserved loan
  const handleCancelLoan = async (loan: LoanResponse) => {
    if (loan.status !== "RESERVED" || loanActionInProgressId !== null) return;

    const confirmed = window.confirm(
      `Cancel reservation for Loan #${loan.id} (Member #${loan.member_id}, Item #${loan.item_id})?\n\nThis will cancel the reservation and release the equipment item back to Available.`,
    );
    if (!confirmed) return;

    setLoanActionInProgressId(loan.id);

    try {
      const updatedLoan = await cancelLoan(loan.id);
      setNotification({
        type: "success",
        message: `Reservation for Loan #${updatedLoan.id} cancelled successfully. Item #${updatedLoan.item_id} is now Available.`,
      });

      // Refresh loans list, equipment catalogue, and member list
      setLoanRefreshTrigger((prev) => prev + 1);
      setItemRefreshTrigger((prev) => prev + 1);
      setMemberRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      let detail = "Cancellation request failed.";
      if (err instanceof ApiClientError) {
        detail = `[${err.code}] ${err.detail || err.error}`;
      } else if (err instanceof Error) {
        detail = err.message;
      }
      setNotification({
        type: "error",
        message: `Could not cancel reservation for Loan #${loan.id}. ${detail}`,
      });
      setLoanRefreshTrigger((prev) => prev + 1);
    } finally {
      setLoanActionInProgressId(null);
    }
  };

  // Item pagination calculations
  const hasActiveItemFilters =
    Boolean(searchInput.trim()) ||
    Boolean(selectedCategory) ||
    Boolean(selectedItemStatus);
  const startItemOffset = items.length > 0 ? itemPage * PAGE_SIZE + 1 : 0;
  const endItemOffset = items.length > 0 ? itemPage * PAGE_SIZE + items.length : 0;

  // Member pagination calculations
  const hasActiveMemberFilters = Boolean(selectedMemberStatus);
  const startMemberOffset = members.length > 0 ? memberPage * PAGE_SIZE + 1 : 0;
  const endMemberOffset = members.length > 0 ? memberPage * PAGE_SIZE + members.length : 0;

  // Loan pagination calculations
  const hasActiveLoanFilters =
    loanViewMode === "all"
      ? Boolean(selectedLoanStatus) ||
        Boolean(debouncedLoanMemberId) ||
        Boolean(debouncedLoanItemId)
      : Boolean(debouncedLoanMemberId) || Boolean(debouncedLoanItemId);
  const startLoanOffset = loans.length > 0 ? loanPage * PAGE_SIZE + 1 : 0;
  const endLoanOffset = loans.length > 0 ? loanPage * PAGE_SIZE + loans.length : 0;

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

          {/* Navigation Tab Bar */}
          <nav className="nav-tabs" role="tablist" aria-label="Main Navigation">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "catalogue"}
              className={`nav-tab-btn ${activeTab === "catalogue" ? "active" : ""}`}
              onClick={() => setActiveTab("catalogue")}
            >
              <span aria-hidden="true">📦</span> Equipment Catalogue
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "members"}
              className={`nav-tab-btn ${activeTab === "members" ? "active" : ""}`}
              onClick={() => setActiveTab("members")}
            >
              <span aria-hidden="true">👥</span> Member Directory
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "loans"}
              className={`nav-tab-btn ${activeTab === "loans" ? "active" : ""}`}
              onClick={() => setActiveTab("loans")}
            >
              <span aria-hidden="true">📋</span> Loans & Reservations
            </button>
          </nav>

          <div className="header-status">
            <span className="api-badge" title={`API endpoint: ${API_BASE_URL ?? "none"}`}>
              API: {API_BASE_URL ?? "local"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content" id="main-content">
        {/* Global Action Notification Banner */}
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

        {/* TAB 1: EQUIPMENT CATALOGUE */}
        {activeTab === "catalogue" && (
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
                  onClick={handleOpenAddItemModal}
                  aria-label="Add new equipment item"
                >
                  <span aria-hidden="true">+</span> Add Item
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-refresh"
                  onClick={handleRefreshItems}
                  disabled={isFetchingItems || itemActionInProgressId !== null}
                  aria-label="Refresh catalogue items"
                >
                  <span
                    className={`refresh-icon ${isFetchingItems ? "spinning" : ""}`}
                    aria-hidden="true"
                  >
                    ↻
                  </span>
                  <span>{isFetchingItems ? "Refreshing…" : "Refresh"}</span>
                </button>
              </div>
            </div>

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
                  onChange={(e) => {
                    setSelectedCategory(e.target.value);
                    setItemPage(0);
                  }}
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
                <label htmlFor={itemStatusSelectId} className="field-label">
                  Status
                </label>
                <select
                  id={itemStatusSelectId}
                  className="select-input"
                  value={selectedItemStatus}
                  onChange={(e) => {
                    setSelectedItemStatus(e.target.value as ItemStatus | "");
                    setItemPage(0);
                  }}
                >
                  {ITEM_STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {hasActiveItemFilters && (
                <div className="filter-actions">
                  <button
                    type="button"
                    className="btn btn-subtle btn-reset"
                    onClick={() => {
                      setSearchInput("");
                      setDebouncedQuery("");
                      setSelectedCategory("");
                      setSelectedItemStatus("");
                      setItemPage(0);
                    }}
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
                {!initialItemsLoading && !itemsError && (
                  <>
                    {items.length === 0 ? (
                      <span className="count-text">0 items found</span>
                    ) : (
                      <span className="count-text">
                        Showing <strong>{startItemOffset}–{endItemOffset}</strong> items
                        {itemPage > 0 && <span className="muted"> (Page {itemPage + 1})</span>}
                      </span>
                    )}
                  </>
                )}
              </div>

              {isFetchingItems && !initialItemsLoading && (
                <span className="fetching-indicator" role="status">
                  Updating results…
                </span>
              )}
            </div>

            {/* UI State: Loading */}
            {initialItemsLoading && (
              <div className="state-panel state-loading" role="status">
                <div className="spinner" aria-hidden="true" />
                <p className="state-title">Loading equipment catalogue…</p>
                <p className="state-subtitle muted">Connecting to rental desk service</p>
              </div>
            )}

            {/* UI State: Error */}
            {!initialItemsLoading && itemsError && (
              <div className="state-panel state-error" role="alert">
                <div className="error-icon" aria-hidden="true">
                  ⚠️
                </div>
                <div className="error-content">
                  <h3 className="error-title">
                    {itemsError instanceof ApiClientError ? itemsError.error : "Failed to load catalogue"}
                  </h3>
                  <p className="error-detail">
                    {itemsError instanceof ApiClientError ? itemsError.detail : itemsError.message}
                  </p>
                  {itemsError instanceof ApiClientError && (
                    <div className="error-meta">
                      <span className="error-code">Code: {itemsError.code}</span>
                      {itemsError.status > 0 && (
                        <span className="error-status">HTTP {itemsError.status}</span>
                      )}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-retry"
                  onClick={handleRefreshItems}
                >
                  Retry
                </button>
              </div>
            )}

            {/* UI State: Empty Catalogue */}
            {!initialItemsLoading && !itemsError && items.length === 0 && !hasActiveItemFilters && (
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
                  onClick={handleOpenAddItemModal}
                >
                  + Add First Equipment Item
                </button>
              </div>
            )}

            {/* UI State: Zero Matches */}
            {!initialItemsLoading && !itemsError && items.length === 0 && hasActiveItemFilters && (
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
                  onClick={() => {
                    setSearchInput("");
                    setDebouncedQuery("");
                    setSelectedCategory("");
                    setSelectedItemStatus("");
                    setItemPage(0);
                  }}
                >
                  Clear All Filters
                </button>
              </div>
            )}

            {/* UI State: Catalogue Table */}
            {!initialItemsLoading && !itemsError && items.length > 0 && (
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
                        const isItemBusy = itemActionInProgressId === item.id;

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
                              <span className={getItemStatusBadgeClass(item.status)}>
                                <span className="status-dot" aria-hidden="true" />
                                {getItemStatusLabel(item.status)}
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
                                  disabled={itemActionInProgressId !== null}
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
                                  disabled={itemActionInProgressId !== null}
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
                    Page <strong>{itemPage + 1}</strong>
                  </div>
                  <div className="pagination-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setItemPage((p) => Math.max(0, p - 1))}
                      disabled={itemPage === 0 || isFetchingItems || itemActionInProgressId !== null}
                      aria-label="Go to previous page"
                    >
                      ← Previous
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setItemPage((p) => p + 1)}
                      disabled={!hasNextItemPage || isFetchingItems || itemActionInProgressId !== null}
                      aria-label="Go to next page"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* TAB 2: MEMBER DIRECTORY */}
        {activeTab === "members" && (
          <section className="members-section" aria-labelledby="members-heading">
            {/* Section Header */}
            <div className="section-header">
              <div>
                <h2 id="members-heading" className="section-title">
                  Member Directory
                </h2>
                <p className="section-description">
                  Manage registered community members, active memberships, account standing, and contact details.
                </p>
              </div>
              <div className="header-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-add-member"
                  onClick={handleOpenAddMemberModal}
                  aria-label="Register new member"
                >
                  <span aria-hidden="true">+</span> Add Member
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-refresh"
                  onClick={handleRefreshMembers}
                  disabled={isFetchingMembers || memberActionInProgressId !== null}
                  aria-label="Refresh member list"
                >
                  <span
                    className={`refresh-icon ${isFetchingMembers ? "spinning" : ""}`}
                    aria-hidden="true"
                  >
                    ↻
                  </span>
                  <span>{isFetchingMembers ? "Refreshing…" : "Refresh"}</span>
                </button>
              </div>
            </div>

            {/* Member Filters Toolbar */}
            <div className="filter-toolbar" role="search" aria-label="Filter member directory">
              <div className="filter-field">
                <label htmlFor={memberStatusSelectId} className="field-label">
                  Member Status
                </label>
                <select
                  id={memberStatusSelectId}
                  className="select-input"
                  value={selectedMemberStatus}
                  onChange={(e) => {
                    setSelectedMemberStatus(e.target.value as MemberStatus | "");
                    setMemberPage(0);
                  }}
                >
                  {MEMBER_STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {hasActiveMemberFilters && (
                <div className="filter-actions">
                  <button
                    type="button"
                    className="btn btn-subtle btn-reset"
                    onClick={() => {
                      setSelectedMemberStatus("");
                      setMemberPage(0);
                    }}
                    title="Clear member status filter"
                  >
                    Clear Filter
                  </button>
                </div>
              )}
            </div>

            {/* Results Summary Bar */}
            <div className="results-bar" aria-live="polite">
              <div className="results-count">
                {!initialMembersLoading && !membersError && (
                  <>
                    {members.length === 0 ? (
                      <span className="count-text">0 members found</span>
                    ) : (
                      <span className="count-text">
                        Showing <strong>{startMemberOffset}–{endMemberOffset}</strong> members
                        {memberPage > 0 && <span className="muted"> (Page {memberPage + 1})</span>}
                      </span>
                    )}
                  </>
                )}
              </div>

              {isFetchingMembers && !initialMembersLoading && (
                <span className="fetching-indicator" role="status">
                  Updating members…
                </span>
              )}
            </div>

            {/* UI State: Loading */}
            {initialMembersLoading && (
              <div className="state-panel state-loading" role="status">
                <div className="spinner" aria-hidden="true" />
                <p className="state-title">Loading member directory…</p>
                <p className="state-subtitle muted">Connecting to rental desk service</p>
              </div>
            )}

            {/* UI State: Error */}
            {!initialMembersLoading && membersError && (
              <div className="state-panel state-error" role="alert">
                <div className="error-icon" aria-hidden="true">
                  ⚠️
                </div>
                <div className="error-content">
                  <h3 className="error-title">
                    {membersError instanceof ApiClientError ? membersError.error : "Failed to load members"}
                  </h3>
                  <p className="error-detail">
                    {membersError instanceof ApiClientError ? membersError.detail : membersError.message}
                  </p>
                  {membersError instanceof ApiClientError && (
                    <div className="error-meta">
                      <span className="error-code">Code: {membersError.code}</span>
                      {membersError.status > 0 && (
                        <span className="error-status">HTTP {membersError.status}</span>
                      )}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-retry"
                  onClick={handleRefreshMembers}
                >
                  Retry
                </button>
              </div>
            )}

            {/* UI State: Empty Member Directory */}
            {!initialMembersLoading && !membersError && members.length === 0 && !hasActiveMemberFilters && (
              <div className="state-panel state-empty">
                <div className="empty-icon" aria-hidden="true">
                  👥
                </div>
                <h3 className="state-title">No members registered yet</h3>
                <p className="state-subtitle muted">
                  The equipment rental library currently has no registered members.
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleOpenAddMemberModal}
                >
                  + Register First Member
                </button>
              </div>
            )}

            {/* UI State: Zero Matches */}
            {!initialMembersLoading && !membersError && members.length === 0 && hasActiveMemberFilters && (
              <div className="state-panel state-empty">
                <div className="empty-icon" aria-hidden="true">
                  🔍
                </div>
                <h3 className="state-title">No matching members found</h3>
                <p className="state-subtitle muted">
                  No members match your active status filter.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setSelectedMemberStatus("");
                    setMemberPage(0);
                  }}
                >
                  Clear Status Filter
                </button>
              </div>
            )}

            {/* UI State: Member Table */}
            {!initialMembersLoading && !membersError && members.length > 0 && (
              <div className="table-card">
                <div className="table-responsive">
                  <table className="catalogue-table" aria-label="Member Directory Items">
                    <thead>
                      <tr>
                        <th scope="col" className="col-id">
                          ID
                        </th>
                        <th scope="col" className="col-name">
                          Member Name
                        </th>
                        <th scope="col" className="col-phone">
                          Phone Number
                        </th>
                        <th scope="col" className="col-status">
                          Account Status
                        </th>
                        <th scope="col" className="col-date">
                          Member Since
                        </th>
                        <th scope="col" className="col-balance text-right">
                          Outstanding Balance
                        </th>
                        <th scope="col" className="col-actions text-center">
                          Account Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((member) => {
                        const isMemberBusy = memberActionInProgressId === member.id;
                        const hasFeeBalance = member.running_fee_balance > 0;

                        return (
                          <tr key={member.id} className="item-row">
                            <td className="col-id font-mono">#{member.id}</td>
                            <td className="col-name">
                              <span className="item-name">{member.name}</span>
                            </td>
                            <td className="col-phone font-mono">
                              <span className="member-phone">{member.phone}</span>
                            </td>
                            <td className="col-status">
                              <span className={getMemberStatusBadgeClass(member.status)}>
                                <span className="status-dot" aria-hidden="true" />
                                {getMemberStatusLabel(member.status)}
                              </span>
                            </td>
                            <td className="col-date">
                              {formatUtcToIst(member.join_date, { includeTime: false })}
                            </td>
                            <td className="col-balance text-right font-mono">
                              <span className={hasFeeBalance ? "balance-due" : "balance-zero"}>
                                {formatPaise(member.running_fee_balance)}
                              </span>
                            </td>
                            <td className="col-actions text-center">
                              <div className="action-button-group">
                                <button
                                  type="button"
                                  className="btn btn-sm btn-action-statement"
                                  onClick={() => handleOpenStatement(member)}
                                  disabled={memberActionInProgressId !== null}
                                  aria-label={`View statement for member #${member.id} (${member.name})`}
                                  title="View account ledger, loans, and fee payments"
                                >
                                  Statement
                                </button>

                                {member.status === "ACTIVE" && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-action-suspend"
                                    onClick={() => handleSuspendMember(member)}
                                    disabled={memberActionInProgressId !== null}
                                    aria-label={`Suspend member #${member.id} (${member.name})`}
                                  >
                                    {isMemberBusy ? "Updating…" : "Suspend"}
                                  </button>
                                )}

                                {member.status === "SUSPENDED" && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-action-reinstate"
                                    onClick={() => handleReinstateMember(member)}
                                    disabled={memberActionInProgressId !== null}
                                    aria-label={`Reinstate member #${member.id} (${member.name})`}
                                  >
                                    {isMemberBusy ? "Updating…" : "Reinstate"}
                                  </button>
                                )}

                                <button
                                  type="button"
                                  className="btn btn-sm btn-action-delete"
                                  onClick={() => handleDeleteMember(member)}
                                  disabled={memberActionInProgressId !== null}
                                  aria-label={`Delete member #${member.id} (${member.name})`}
                                  title="Delete member if no loan/payment history"
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination Controls */}
                <div className="pagination-bar" aria-label="Member directory pagination">
                  <div className="pagination-info muted">
                    Page <strong>{memberPage + 1}</strong>
                  </div>
                  <div className="pagination-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setMemberPage((p) => Math.max(0, p - 1))}
                      disabled={memberPage === 0 || isFetchingMembers || memberActionInProgressId !== null}
                      aria-label="Go to previous page"
                    >
                      ← Previous
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setMemberPage((p) => p + 1)}
                      disabled={!hasNextMemberPage || isFetchingMembers || memberActionInProgressId !== null}
                      aria-label="Go to next page"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* TAB 3: LOAN MANAGEMENT */}
        {activeTab === "loans" && (
          <section className="loans-section" aria-labelledby="loans-heading">
            {/* Section Header */}
            <div className="section-header">
              <div>
                <h2 id="loans-heading" className="section-title">
                  Loans & Reservations
                </h2>
                <p className="section-description">
                  {loanViewMode === "overdue"
                    ? "Identify and process overdue equipment loans requiring return."
                    : "Manage equipment reservations, checkouts, loan periods, and monitor return statuses."}
                </p>
              </div>
              <div className="header-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-reserve-equipment"
                  onClick={handleOpenReserveModal}
                  aria-label="Create new equipment reservation"
                >
                  <span aria-hidden="true">+</span> Reserve Equipment
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-refresh"
                  onClick={() => {
                    if (!isFetchingLoans) setLoanRefreshTrigger((prev) => prev + 1);
                  }}
                  disabled={isFetchingLoans || loanActionInProgressId !== null}
                  aria-label="Refresh loan list"
                >
                  <span
                    className={`refresh-icon ${isFetchingLoans ? "spinning" : ""}`}
                    aria-hidden="true"
                  >
                    ↻
                  </span>
                  <span>{isFetchingLoans ? "Refreshing…" : "Refresh"}</span>
                </button>
              </div>
            </div>

            {/* Loan View Mode Subtabs (All vs Overdue) */}
            <div className="loan-tabs-header" role="tablist" aria-label="Loan view filters">
              <button
                type="button"
                role="tab"
                aria-selected={loanViewMode === "all"}
                className={`subtab-btn ${loanViewMode === "all" ? "active" : ""}`}
                onClick={() => {
                  if (loanViewMode !== "all") {
                    setLoanViewMode("all");
                    setLoanPage(0);
                  }
                }}
              >
                All Loans & History
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={loanViewMode === "overdue"}
                className={`subtab-btn subtab-btn-danger ${loanViewMode === "overdue" ? "active" : ""}`}
                onClick={() => {
                  if (loanViewMode !== "overdue") {
                    setLoanViewMode("overdue");
                    setLoanPage(0);
                  }
                }}
              >
                ⚠️ Overdue Loans Only
              </button>
            </div>

            {loanViewMode === "overdue" && (
              <div className="overdue-banner" role="status">
                <span aria-hidden="true">⚠️</span>
                <span>
                  Showing currently overdue loans from <code>GET /loans/overdue</code>. Due dates have passed according to system clock. Returning an item will calculate and assess late fees (₹10/calendar day, capped at ₹200 and replacement value).
                </span>
              </div>
            )}

            {/* Filters Toolbar */}
            <div className="filter-toolbar" role="search" aria-label="Filter loans directory">
              {loanViewMode === "all" ? (
                <div className="filter-field">
                  <label htmlFor={loanStatusSelectId} className="field-label">
                    Loan Status
                  </label>
                  <select
                    id={loanStatusSelectId}
                    className="select-input"
                    value={selectedLoanStatus}
                    onChange={(e) => {
                      setSelectedLoanStatus(e.target.value as LoanStatus | "");
                      setLoanPage(0);
                    }}
                  >
                    {LOAN_STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="filter-field">
                  <label htmlFor={loanStatusSelectId} className="field-label">
                    Loan Status
                  </label>
                  <input
                    id={loanStatusSelectId}
                    type="text"
                    className="input-text"
                    value="CHECKED_OUT (Overdue)"
                    disabled
                    readOnly
                    title="All loans in this view are currently overdue checked-out loans"
                  />
                </div>
              )}

              <div className="filter-field">
                <label htmlFor={loanMemberIdInputId} className="field-label">
                  Filter by Member ID
                </label>
                <input
                  id={loanMemberIdInputId}
                  type="number"
                  min="1"
                  className="input-text"
                  placeholder="e.g. 1"
                  value={loanMemberIdFilter}
                  onChange={(e) => setLoanMemberIdFilter(e.target.value)}
                />
              </div>

              <div className="filter-field">
                <label htmlFor={loanItemIdInputId} className="field-label">
                  Filter by Item ID
                </label>
                <input
                  id={loanItemIdInputId}
                  type="number"
                  min="1"
                  className="input-text"
                  placeholder="e.g. 10"
                  value={loanItemIdFilter}
                  onChange={(e) => setLoanItemIdFilter(e.target.value)}
                />
              </div>

              {hasActiveLoanFilters && (
                <div className="filter-actions">
                  <button
                    type="button"
                    className="btn btn-subtle btn-reset"
                    onClick={() => {
                      if (loanViewMode === "all") setSelectedLoanStatus("");
                      setLoanMemberIdFilter("");
                      setLoanItemIdFilter("");
                      setLoanPage(0);
                    }}
                    title="Clear all active loan filters"
                  >
                    Clear Filters
                  </button>
                </div>
              )}
            </div>

            {/* Results Summary Bar */}
            <div className="results-bar" aria-live="polite">
              <div className="results-count">
                {!initialLoansLoading && !loansError && (
                  <>
                    {loans.length === 0 ? (
                      <span className={`count-text ${loanViewMode === "overdue" ? "count-text-success" : ""}`}>
                        {loanViewMode === "overdue" ? "✓ 0 overdue loans found" : "0 loans found"}
                      </span>
                    ) : (
                      <span className={`count-text ${loanViewMode === "overdue" ? "count-text-danger" : ""}`}>
                        {loanViewMode === "overdue" ? "⚠️ Showing " : "Showing "}
                        <strong>{startLoanOffset}–{endLoanOffset}</strong>
                        {loanViewMode === "overdue" ? " overdue loans" : " loans"}
                        {loanPage > 0 && <span className="muted"> (Page {loanPage + 1})</span>}
                      </span>
                    )}
                  </>
                )}
              </div>

              {isFetchingLoans && !initialLoansLoading && (
                <span className="fetching-indicator" role="status">
                  {loanViewMode === "overdue" ? "Updating overdue loans…" : "Updating loans…"}
                </span>
              )}
            </div>

            {/* UI State: Loading */}
            {initialLoansLoading && (
              <div className="state-panel state-loading" role="status">
                <div className="spinner" aria-hidden="true" />
                <p className="state-title">
                  {loanViewMode === "overdue" ? "Loading overdue loans…" : "Loading loan directory…"}
                </p>
                <p className="state-subtitle muted">Connecting to rental desk service</p>
              </div>
            )}

            {/* UI State: Error */}
            {!initialLoansLoading && loansError && (
              <div className="state-panel state-error" role="alert">
                <div className="error-icon" aria-hidden="true">
                  ⚠️
                </div>
                <div className="error-content">
                  <h3 className="error-title">
                    {loansError instanceof ApiClientError ? loansError.error : "Failed to load loans"}
                  </h3>
                  <p className="error-detail">
                    {loansError instanceof ApiClientError ? loansError.detail : loansError.message}
                  </p>
                  {loansError instanceof ApiClientError && (
                    <div className="error-meta">
                      <span className="error-code">Code: {loansError.code}</span>
                      {loansError.status > 0 && (
                        <span className="error-status">HTTP {loansError.status}</span>
                      )}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-retry"
                  onClick={() => setLoanRefreshTrigger((prev) => prev + 1)}
                >
                  Retry
                </button>
              </div>
            )}

            {/* UI State: Empty Directory */}
            {!initialLoansLoading && !loansError && loans.length === 0 && !hasActiveLoanFilters && (
              <div className="state-panel state-empty">
                <div className="empty-icon" aria-hidden="true">
                  {loanViewMode === "overdue" ? "🎉" : "📋"}
                </div>
                <h3 className="state-title">
                  {loanViewMode === "overdue" ? "No overdue loans" : "No loans recorded yet"}
                </h3>
                <p className="state-subtitle muted">
                  {loanViewMode === "overdue"
                    ? "All checked-out equipment items are within their 7-day loan window, or have already been returned."
                    : "No equipment reservations or loans have been created yet."}
                </p>
                {loanViewMode === "overdue" ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setLoanViewMode("all");
                      setLoanPage(0);
                    }}
                  >
                    View All Loans
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleOpenReserveModal}
                  >
                    + Reserve First Equipment Item
                  </button>
                )}
              </div>
            )}

            {/* UI State: Zero Matches */}
            {!initialLoansLoading && !loansError && loans.length === 0 && hasActiveLoanFilters && (
              <div className="state-panel state-empty">
                <div className="empty-icon" aria-hidden="true">
                  🔍
                </div>
                <h3 className="state-title">No matching loans found</h3>
                <p className="state-subtitle muted">
                  {loanViewMode === "overdue"
                    ? "No overdue loans match your active member or item ID filters."
                    : "No loans match your active status or ID filters."}
                </p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    if (loanViewMode === "all") setSelectedLoanStatus("");
                    setLoanMemberIdFilter("");
                    setLoanItemIdFilter("");
                    setLoanPage(0);
                  }}
                >
                  Clear Filters
                </button>
              </div>
            )}

            {/* UI State: Loans Table */}
            {!initialLoansLoading && !loansError && loans.length > 0 && (
              <div className="table-card">
                <div className="table-responsive">
                  <table
                    className="catalogue-table"
                    aria-label={loanViewMode === "overdue" ? "Overdue Loans Directory" : "Loans Directory"}
                  >
                    <thead>
                      <tr>
                        <th scope="col" className="col-id">
                          Loan ID
                        </th>
                        <th scope="col">Member</th>
                        <th scope="col">Equipment Item</th>
                        <th scope="col">Loan Status</th>
                        <th scope="col">Reserved At</th>
                        <th scope="col">Checked Out</th>
                        <th scope="col">Due Date</th>
                        <th scope="col">Return / Cancel</th>
                        <th scope="col" className="text-right">
                          Fee Charged
                        </th>
                        <th scope="col" className="col-actions text-center">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {loans.map((loan) => {
                        const isLoanBusy = loanActionInProgressId === loan.id;
                        const canCheckout = isLoanActionAllowed(loan.status, "checkout");
                        const canCancel = isLoanActionAllowed(loan.status, "cancel");
                        const canReturn = isLoanActionAllowed(loan.status, "return");
                        const isOverdue = loanViewMode === "overdue";

                        return (
                          <tr key={loan.id} className="item-row">
                            <td className="col-id font-mono">#{loan.id}</td>
                            <td className="font-mono">
                              <span className="badge-subtle">Member #{loan.member_id}</span>
                            </td>
                            <td className="font-mono">
                              <span className="badge-subtle">Item #{loan.item_id}</span>
                            </td>
                            <td>
                              <span className={getLoanStatusBadgeClass(loan.status, isOverdue)}>
                                <span className="status-dot" aria-hidden="true" />
                                {getLoanStatusLabel(loan.status, isOverdue)}
                              </span>
                            </td>
                            <td>{formatUtcToIst(loan.reserved_at)}</td>
                            <td>
                              {loan.checked_out_at ? formatUtcToIst(loan.checked_out_at) : "—"}
                            </td>
                            <td>{loan.due_at ? formatUtcToIst(loan.due_at) : "—"}</td>
                            <td>
                              {loan.returned_at
                                ? formatUtcToIst(loan.returned_at)
                                : loan.cancelled_at
                                ? `Cancelled: ${formatUtcToIst(loan.cancelled_at)}`
                                : "—"}
                            </td>
                            <td className="text-right font-mono">
                              <span
                                className={
                                  loan.fee_charged > 0 ? "balance-due" : "balance-zero"
                                }
                              >
                                {formatPaise(loan.fee_charged)}
                              </span>
                            </td>
                            <td className="col-actions text-center">
                              <div className="action-button-group">
                                {canCheckout && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-action-checkout"
                                    onClick={() => handleCheckoutLoan(loan)}
                                    disabled={loanActionInProgressId !== null}
                                    aria-label={`Check out equipment for Loan #${loan.id}`}
                                    title="Check out equipment item (starts 7-day loan period)"
                                  >
                                    {isLoanBusy ? "Checking out…" : "Check Out"}
                                  </button>
                                )}
                                {canCancel && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-action-cancel"
                                    onClick={() => handleCancelLoan(loan)}
                                    disabled={loanActionInProgressId !== null}
                                    aria-label={`Cancel reservation for Loan #${loan.id}`}
                                    title="Cancel reservation and return item to Available"
                                  >
                                    {isLoanBusy ? "Cancelling…" : "Cancel"}
                                  </button>
                                )}
                                {canReturn && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-action-return"
                                    onClick={() => handleReturnLoan(loan)}
                                    disabled={loanActionInProgressId !== null}
                                    aria-label={`Return equipment for Loan #${loan.id}`}
                                    title="Return equipment item and assess any late fees"
                                  >
                                    {isLoanBusy ? "Returning…" : "Return"}
                                  </button>
                                )}
                                {!canCheckout && !canCancel && !canReturn && (
                                  <span className="action-inactive">Completed</span>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination Controls */}
                <div className="pagination-bar" aria-label="Loans pagination">
                  <div className="pagination-info muted">
                    Page <strong>{loanPage + 1}</strong>
                  </div>
                  <div className="pagination-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setLoanPage((p) => Math.max(0, p - 1))}
                      disabled={loanPage === 0 || isFetchingLoans || loanActionInProgressId !== null}
                      aria-label="Go to previous loans page"
                    >
                      ← Previous
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-pagination"
                      onClick={() => setLoanPage((p) => p + 1)}
                      disabled={!hasNextLoanPage || isFetchingLoans || loanActionInProgressId !== null}
                      aria-label="Go to next loans page"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}
      </main>

      {/* Add Item Modal Dialog */}
      {isAddItemModalOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !isSubmittingItem) {
              handleCloseAddItemModal();
            }
          }}
          aria-hidden={!isAddItemModalOpen}
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
                onClick={handleCloseAddItemModal}
                disabled={isSubmittingItem}
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateItemSubmit} noValidate>
              <div className="modal-body">
                {itemFormApiError && (
                  <div className="form-alert-error" role="alert">
                    <span aria-hidden="true">⚠️</span>
                    <span>{itemFormApiError}</span>
                  </div>
                )}

                {/* Item Name */}
                <div className="form-group">
                  <label htmlFor="item-form-name" className="field-label">
                    Equipment Name <span className="required-star">*</span>
                  </label>
                  <input
                    ref={itemNameInputRef}
                    id="item-form-name"
                    type="text"
                    className={`input-text ${itemFormErrors.name ? "input-error" : ""}`}
                    placeholder="e.g. Cordless Drill 18V"
                    value={itemFormValues.name}
                    onChange={(e) => handleItemFormFieldChange("name", e.target.value)}
                    disabled={isSubmittingItem}
                    maxLength={255}
                    required
                  />
                  {itemFormErrors.name && (
                    <p className="field-error" role="alert">
                      {itemFormErrors.name}
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
                    className={`input-text ${itemFormErrors.category ? "input-error" : ""}`}
                    placeholder="e.g. Drills, Saws, Ladders"
                    value={itemFormValues.category}
                    onChange={(e) => handleItemFormFieldChange("category", e.target.value)}
                    disabled={isSubmittingItem}
                    maxLength={100}
                    required
                  />
                  <datalist id="category-suggestions">
                    {availableCategories.map((cat) => (
                      <option key={cat} value={cat} />
                    ))}
                  </datalist>
                  {itemFormErrors.category && (
                    <p className="field-error" role="alert">
                      {itemFormErrors.category}
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
                      className={`input-text currency-input ${itemFormErrors.replacement_value ? "input-error" : ""}`}
                      placeholder="e.g. 4500 or 4500.00"
                      value={itemFormValues.replacement_value}
                      onChange={(e) =>
                        handleItemFormFieldChange("replacement_value", e.target.value)
                      }
                      disabled={isSubmittingItem}
                      required
                    />
                  </div>
                  {itemFormErrors.replacement_value ? (
                    <p className="field-error" role="alert">
                      {itemFormErrors.replacement_value}
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
                    className={`textarea-input ${itemFormErrors.condition_note ? "input-error" : ""}`}
                    rows={3}
                    placeholder="e.g. Includes two 2Ah batteries and charger. Serial #D-1029."
                    value={itemFormValues.condition_note}
                    onChange={(e) =>
                      handleItemFormFieldChange("condition_note", e.target.value)
                    }
                    disabled={isSubmittingItem}
                    maxLength={2000}
                  />
                  {itemFormErrors.condition_note && (
                    <p className="field-error" role="alert">
                      {itemFormErrors.condition_note}
                    </p>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCloseAddItemModal}
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

      {/* Add Member Modal Dialog */}
      {isAddMemberModalOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !isSubmittingMember) {
              handleCloseAddMemberModal();
            }
          }}
          aria-hidden={!isAddMemberModalOpen}
        >
          <div
            className="modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-member-modal-title"
          >
            <div className="modal-header">
              <h3 id="add-member-modal-title" className="modal-title">
                Register New Member
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleCloseAddMemberModal}
                disabled={isSubmittingMember}
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateMemberSubmit} noValidate>
              <div className="modal-body">
                {memberFormApiError && (
                  <div className="form-alert-error" role="alert">
                    <span aria-hidden="true">⚠️</span>
                    <span>{memberFormApiError}</span>
                  </div>
                )}

                {/* Member Name */}
                <div className="form-group">
                  <label htmlFor="member-form-name" className="field-label">
                    Full Name <span className="required-star">*</span>
                  </label>
                  <input
                    ref={memberNameInputRef}
                    id="member-form-name"
                    type="text"
                    className={`input-text ${memberFormErrors.name ? "input-error" : ""}`}
                    placeholder="e.g. Priya Patel"
                    value={memberFormValues.name}
                    onChange={(e) => handleMemberFormFieldChange("name", e.target.value)}
                    disabled={isSubmittingMember}
                    maxLength={255}
                    required
                  />
                  {memberFormErrors.name && (
                    <p className="field-error" role="alert">
                      {memberFormErrors.name}
                    </p>
                  )}
                </div>

                {/* Phone Number */}
                <div className="form-group">
                  <label htmlFor="member-form-phone" className="field-label">
                    Contact Phone <span className="required-star">*</span>
                  </label>
                  <input
                    id="member-form-phone"
                    type="tel"
                    className={`input-text ${memberFormErrors.phone ? "input-error" : ""}`}
                    placeholder="e.g. +91-98000-00002 or 9876543210"
                    value={memberFormValues.phone}
                    onChange={(e) => handleMemberFormFieldChange("phone", e.target.value)}
                    disabled={isSubmittingMember}
                    maxLength={64}
                    required
                  />
                  {memberFormErrors.phone ? (
                    <p className="field-error" role="alert">
                      {memberFormErrors.phone}
                    </p>
                  ) : (
                    <p className="field-hint muted">
                      Accepts standard formats (up to 64 characters, single line).
                    </p>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCloseAddMemberModal}
                  disabled={isSubmittingMember}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary btn-submit-member"
                  disabled={isSubmittingMember}
                >
                  {isSubmittingMember ? (
                    <>
                      <span className="spinner-sm" aria-hidden="true" />
                      <span>Registering…</span>
                    </>
                  ) : (
                    "Register Member"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Member Statement Modal Dialog */}
      {selectedStatementMember && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !isSubmittingPayment) {
              handleCloseStatement();
            }
          }}
          aria-hidden={!selectedStatementMember}
        >
          <div
            className="modal-dialog statement-modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="statement-modal-title"
          >
            <div className="modal-header">
              <div>
                <h3 id="statement-modal-title" className="modal-title">
                  Account Statement — {selectedStatementMember.name}
                </h3>
                <p className="modal-subtitle muted">
                  Member #{selectedStatementMember.id} · Phone: {selectedStatementMember.phone} · Joined:{" "}
                  {formatUtcToIst(selectedStatementMember.join_date, { includeTime: false })}
                </p>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleCloseStatement}
                disabled={isSubmittingPayment}
                aria-label="Close statement dialog"
              >
                ×
              </button>
            </div>

            <div className="modal-body statement-modal-body">
              {/* Statement Loading State */}
              {isStatementLoading && !statementData && (
                <div className="state-panel state-loading" role="status">
                  <div className="spinner" aria-hidden="true" />
                  <p className="state-title">Loading member statement…</p>
                  <p className="state-subtitle muted">Fetching rental ledger and transaction records</p>
                </div>
              )}

              {/* Statement Error State */}
              {!isStatementLoading && statementError && (
                <div className="state-panel state-error" role="alert">
                  <div className="error-icon" aria-hidden="true">
                    ⚠️
                  </div>
                  <div className="error-content">
                    <h4 className="error-title">
                      {statementError instanceof ApiClientError
                        ? statementError.error
                        : "Failed to load statement"}
                    </h4>
                    <p className="error-detail">
                      {statementError instanceof ApiClientError
                        ? statementError.detail
                        : statementError.message}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary btn-retry"
                    onClick={handleRefreshStatement}
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Loaded Statement View */}
              {statementData && (
                <>
                  {/* Summary Metrics Grid */}
                  <div className="statement-summary-grid">
                    <div
                      className={`statement-stat-card ${
                        statementData.current_outstanding_balance > 0 ? "stat-card-alert" : ""
                      }`}
                    >
                      <span className="stat-card-label">Outstanding Balance</span>
                      <span className="stat-card-value font-mono">
                        {formatPaise(statementData.current_outstanding_balance)}
                      </span>
                      <span className="stat-card-hint">
                        {statementData.current_outstanding_balance > 0
                          ? "Late fees pending payment"
                          : "Account in good standing (₹0.00)"}
                      </span>
                    </div>

                    <div className="statement-stat-card">
                      <span className="stat-card-label">Total Fees Assessed</span>
                      <span className="stat-card-value font-mono">
                        {formatPaise(statementData.total_fees_charged)}
                      </span>
                      <span className="stat-card-hint">Cumulative overdue fee charges</span>
                    </div>

                    <div className="statement-stat-card">
                      <span className="stat-card-label">Total Payments Received</span>
                      <span className="stat-card-value font-mono">
                        {formatPaise(statementData.total_payments_recorded)}
                      </span>
                      <span className="stat-card-hint">
                        {statementData.payments.length} payment
                        {statementData.payments.length === 1 ? "" : "s"} recorded
                      </span>
                    </div>
                  </div>

                  {/* Fee Payment Section */}
                  <div className="statement-payment-section">
                    {!isPaymentFormOpen ? (
                      <div className="statement-payment-bar">
                        <div>
                          <h4 className="payment-bar-title">Fee Payment</h4>
                          <p className="payment-bar-desc muted">
                            {statementData.current_outstanding_balance > 0
                              ? `Outstanding balance of ${formatPaise(
                                  statementData.current_outstanding_balance,
                                )} can be paid down.`
                              : "This member account currently has no outstanding fee balance (₹0.00)."}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn btn-primary btn-record-payment"
                          onClick={() => setIsPaymentFormOpen(true)}
                          disabled={statementData.current_outstanding_balance <= 0}
                          title={
                            statementData.current_outstanding_balance <= 0
                              ? "No outstanding fee balance to pay"
                              : "Record a fee payment"
                          }
                        >
                          💳 Record Fee Payment
                        </button>
                      </div>
                    ) : (
                      <div
                        className="payment-form-card"
                        role="region"
                        aria-label="Record Fee Payment Form"
                      >
                        <div className="payment-form-header">
                          <h4 className="payment-form-title">Record Fee Payment</h4>
                          <button
                            type="button"
                            className="btn btn-subtle btn-sm"
                            onClick={() => {
                              setIsPaymentFormOpen(false);
                              setPaymentFormErrors({});
                              setPaymentFormApiError(null);
                            }}
                            disabled={isSubmittingPayment}
                          >
                            Cancel
                          </button>
                        </div>

                        <p className="payment-form-note muted">
                          Payments immediately reduce the member's running fee balance. Payments cannot
                          exceed the outstanding balance of{" "}
                          <strong>{formatPaise(statementData.current_outstanding_balance)}</strong>.
                          Overpayments and negative fee balances are rejected by the system.
                        </p>

                        <form onSubmit={handleRecordPaymentSubmit} noValidate>
                          {paymentFormApiError && (
                            <div className="form-alert-error" role="alert">
                              <span aria-hidden="true">⚠️</span>
                              <span>{paymentFormApiError}</span>
                            </div>
                          )}

                          <div className="payment-form-fields">
                            <div className="form-group flex-1">
                              <div className="form-label-row">
                                <label htmlFor="payment-amount" className="field-label">
                                  Amount (₹) <span className="required-star">*</span>
                                </label>
                                <button
                                  type="button"
                                  className="btn-link btn-pay-full"
                                  onClick={handlePayFullBalance}
                                  disabled={isSubmittingPayment}
                                >
                                  Pay Full ({formatPaise(statementData.current_outstanding_balance)})
                                </button>
                              </div>
                              <div className="currency-input-wrapper">
                                <span className="currency-symbol" aria-hidden="true">
                                  ₹
                                </span>
                                <input
                                  ref={paymentAmountInputRef}
                                  id="payment-amount"
                                  type="text"
                                  className={`input-text currency-input ${
                                    paymentFormErrors.amount ? "input-error" : ""
                                  }`}
                                  placeholder="0.00"
                                  value={paymentFormValues.amount}
                                  onChange={(e) =>
                                    handlePaymentFormFieldChange("amount", e.target.value)
                                  }
                                  disabled={isSubmittingPayment}
                                  autoComplete="off"
                                  required
                                />
                              </div>
                              {paymentFormErrors.amount && (
                                <p className="field-error" role="alert">
                                  {paymentFormErrors.amount}
                                </p>
                              )}
                            </div>

                            <div className="form-group flex-2">
                              <label htmlFor="payment-note" className="field-label">
                                Payment Note <span className="optional-tag">(Optional)</span>
                              </label>
                              <input
                                id="payment-note"
                                type="text"
                                className={`input-text ${
                                  paymentFormErrors.note ? "input-error" : ""
                                }`}
                                placeholder="e.g. UPI Ref #987654321 or Cash Desk"
                                value={paymentFormValues.note || ""}
                                onChange={(e) =>
                                  handlePaymentFormFieldChange("note", e.target.value)
                                }
                                disabled={isSubmittingPayment}
                                maxLength={255}
                              />
                              {paymentFormErrors.note && (
                                <p className="field-error" role="alert">
                                  {paymentFormErrors.note}
                                </p>
                              )}
                            </div>
                          </div>

                          <div className="payment-form-actions">
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={() => {
                                setIsPaymentFormOpen(false);
                                setPaymentFormErrors({});
                                setPaymentFormApiError(null);
                              }}
                              disabled={isSubmittingPayment}
                            >
                              Cancel
                            </button>
                            <button
                              type="submit"
                              className="btn btn-primary"
                              disabled={isSubmittingPayment}
                            >
                              {isSubmittingPayment ? (
                                <>
                                  <span className="spinner-sm" aria-hidden="true" />
                                  <span>Recording Payment…</span>
                                </>
                              ) : (
                                "Submit Payment"
                              )}
                            </button>
                          </div>
                        </form>
                      </div>
                    )}
                  </div>

                  {/* Subtabs for Statement History */}
                  <div className="statement-tabs-header">
                    <div
                      className="statement-subtabs"
                      role="tablist"
                      aria-label="Statement History Sections"
                    >
                      <button
                        type="button"
                        role="tab"
                        aria-selected={activeStatementTab === "loans"}
                        className={`subtab-btn ${activeStatementTab === "loans" ? "active" : ""}`}
                        onClick={() => setActiveStatementTab("loans")}
                      >
                        📦 Loan & Late Fee History ({statementData.loans.length})
                      </button>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={activeStatementTab === "payments"}
                        className={`subtab-btn ${
                          activeStatementTab === "payments" ? "active" : ""
                        }`}
                        onClick={() => setActiveStatementTab("payments")}
                      >
                        💳 Recorded Payments ({statementData.payments.length})
                      </button>
                    </div>
                  </div>

                  {/* TAB 1: LOANS & FEES */}
                  {activeStatementTab === "loans" && (
                    <div className="statement-table-wrapper">
                      {statementData.loans.length === 0 ? (
                        <div className="statement-empty-state muted">
                          No loan records found for this member.
                        </div>
                      ) : (
                        <table
                          className="catalogue-table statement-table"
                          aria-label="Member Loan Activity"
                        >
                          <thead>
                            <tr>
                              <th scope="col" className="col-id">
                                Loan ID
                              </th>
                              <th scope="col">Item ID</th>
                              <th scope="col">Loan Status</th>
                              <th scope="col">Reserved At</th>
                              <th scope="col">Checked Out</th>
                              <th scope="col">Due Date</th>
                              <th scope="col">Return / Cancel</th>
                              <th scope="col" className="text-right">
                                Fee Charged
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {statementData.loans.map((loan) => (
                              <tr key={loan.id} className="item-row">
                                <td className="col-id font-mono">#{loan.id}</td>
                                <td className="font-mono">Item #{loan.item_id}</td>
                                <td>
                                  <span className={getLoanStatusBadgeClass(loan.status)}>
                                    <span className="status-dot" aria-hidden="true" />
                                    {getLoanStatusLabel(loan.status)}
                                  </span>
                                </td>
                                <td>{formatUtcToIst(loan.reserved_at)}</td>
                                <td>
                                  {loan.checked_out_at
                                    ? formatUtcToIst(loan.checked_out_at)
                                    : "—"}
                                </td>
                                <td>{loan.due_at ? formatUtcToIst(loan.due_at) : "—"}</td>
                                <td>
                                  {loan.returned_at
                                    ? formatUtcToIst(loan.returned_at)
                                    : loan.cancelled_at
                                    ? `Cancelled: ${formatUtcToIst(loan.cancelled_at)}`
                                    : "—"}
                                </td>
                                <td className="text-right font-mono">
                                  <span
                                    className={
                                      loan.fee_charged > 0 ? "balance-due" : "balance-zero"
                                    }
                                  >
                                    {formatPaise(loan.fee_charged)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}

                  {/* TAB 2: PAYMENTS */}
                  {activeStatementTab === "payments" && (
                    <div className="statement-table-wrapper">
                      {statementData.payments.length === 0 ? (
                        <div className="statement-empty-state muted">
                          No payment records found for this member.
                        </div>
                      ) : (
                        <table
                          className="catalogue-table statement-table"
                          aria-label="Member Payment History"
                        >
                          <thead>
                            <tr>
                              <th scope="col" className="col-id">
                                Payment ID
                              </th>
                              <th scope="col">Date Paid (IST)</th>
                              <th scope="col" className="text-right">
                                Amount Paid
                              </th>
                              <th scope="col">Payment Note / Reference</th>
                            </tr>
                          </thead>
                          <tbody>
                            {statementData.payments.map((payment) => (
                              <tr key={payment.id} className="item-row">
                                <td className="col-id font-mono">#{payment.id}</td>
                                <td>{formatUtcToIst(payment.paid_at)}</td>
                                <td className="text-right font-mono font-semibold">
                                  {formatPaise(payment.amount)}
                                </td>
                                <td>
                                  {payment.note ? (
                                    <span className="payment-note-text">{payment.note}</span>
                                  ) : (
                                    <span className="muted">—</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleCloseStatement}
                disabled={isSubmittingPayment}
              >
                Close Statement
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reserve Equipment Modal Dialog */}
      {isReserveModalOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !isSubmittingReserve) {
              handleCloseReserveModal();
            }
          }}
          aria-hidden={!isReserveModalOpen}
        >
          <div
            className="modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reserve-modal-title"
          >
            <div className="modal-header">
              <h3 id="reserve-modal-title" className="modal-title">
                Reserve Equipment Item
              </h3>
              <button
                type="button"
                className="modal-close-btn"
                onClick={handleCloseReserveModal}
                disabled={isSubmittingReserve}
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleReserveFormSubmit} noValidate>
              <div className="modal-body">
                {reserveFormApiError && (
                  <div className="form-alert-error" role="alert">
                    <span aria-hidden="true">⚠️</span>
                    <div style={{ flex: 1 }}>
                      <span>{reserveFormApiError}</span>
                    </div>
                    {activeMembersForReserve.length === 0 && availableItemsForReserve.length === 0 && (
                      <button
                        type="button"
                        className="btn btn-alert-retry"
                        onClick={loadReserveOptions}
                        disabled={isLoadingReserveOptions || isSubmittingReserve}
                      >
                        {isLoadingReserveOptions ? "Retrying…" : "Retry"}
                      </button>
                    )}
                  </div>
                )}

                <p className="field-hint muted">
                  Select an active member and an available equipment item. Reservations are held for
                  48 hours from creation.
                </p>

                {/* Member Selection */}
                <div className="form-group">
                  <label htmlFor="reserve-member-select" className="field-label">
                    Member <span className="required-star">*</span>
                  </label>
                  <select
                    id="reserve-member-select"
                    className={`select-input ${reserveFormErrors.member_id ? "input-error" : ""}`}
                    value={reserveFormValues.member_id}
                    onChange={(e) => {
                      const val = e.target.value;
                      setReserveFormValues((prev) => ({ ...prev, member_id: val }));
                      if (reserveFormErrors.member_id) {
                        setReserveFormErrors((prev) => {
                          const next = { ...prev };
                          delete next.member_id;
                          return next;
                        });
                      }
                      if (reserveFormApiError) setReserveFormApiError(null);
                    }}
                    disabled={isSubmittingReserve || isLoadingReserveOptions}
                    required
                  >
                    <option value="">
                      {isLoadingReserveOptions
                        ? "Loading active members…"
                        : reserveFormApiError && activeMembersForReserve.length === 0
                        ? "Failed to load active members"
                        : activeMembersForReserve.length === 0
                        ? "No active members available"
                        : "-- Select a Member --"}
                    </option>
                    {activeMembersForReserve.map((m) => (
                      <option key={m.id} value={m.id}>
                        #{m.id} · {m.name} ({m.phone}){" "}
                        {m.running_fee_balance > 0
                          ? `[Dues: ${formatPaise(m.running_fee_balance)}]`
                          : ""}
                      </option>
                    ))}
                  </select>
                  {reserveFormErrors.member_id && (
                    <p className="field-error" role="alert">
                      {reserveFormErrors.member_id}
                    </p>
                  )}
                </div>

                {/* Equipment Item Selection */}
                <div className="form-group">
                  <label htmlFor="reserve-item-select" className="field-label">
                    Equipment Item <span className="required-star">*</span>
                  </label>
                  <select
                    id="reserve-item-select"
                    className={`select-input ${reserveFormErrors.item_id ? "input-error" : ""}`}
                    value={reserveFormValues.item_id}
                    onChange={(e) => {
                      const val = e.target.value;
                      setReserveFormValues((prev) => ({ ...prev, item_id: val }));
                      if (reserveFormErrors.item_id) {
                        setReserveFormErrors((prev) => {
                          const next = { ...prev };
                          delete next.item_id;
                          return next;
                        });
                      }
                      if (reserveFormApiError) setReserveFormApiError(null);
                    }}
                    disabled={isSubmittingReserve || isLoadingReserveOptions}
                    required
                  >
                    <option value="">
                      {isLoadingReserveOptions
                        ? "Loading available equipment…"
                        : reserveFormApiError && availableItemsForReserve.length === 0
                        ? "Failed to load available equipment"
                        : availableItemsForReserve.length === 0
                        ? "No available items (all items reserved, loaned, or in maintenance)"
                        : "-- Select an Available Equipment Item --"}
                    </option>
                    {availableItemsForReserve.map((item) => (
                      <option key={item.id} value={item.id}>
                        #{item.id} · {item.name} [{item.category}] (
                        {formatPaise(item.replacement_value)})
                      </option>
                    ))}
                  </select>
                  {reserveFormErrors.item_id && (
                    <p className="field-error" role="alert">
                      {reserveFormErrors.item_id}
                    </p>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCloseReserveModal}
                  disabled={isSubmittingReserve}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={
                    isSubmittingReserve ||
                    isLoadingReserveOptions ||
                    availableItemsForReserve.length === 0 ||
                    activeMembersForReserve.length === 0
                  }
                >
                  {isSubmittingReserve ? (
                    <>
                      <span className="spinner-sm" aria-hidden="true" />
                      <span>Reserving…</span>
                    </>
                  ) : (
                    "Confirm Reservation"
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
