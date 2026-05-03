async function api(path, method = "GET", data = null) {
  try {
    const opts = { method, credentials: "include" };
    if (data) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(data);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Request failed");
    }
    return await res.json();
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

function toast(message, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = message;
  t.className = `fixed top-4 right-4 px-6 py-3 rounded-2xl shadow-xl z-50 transition-all transform translate-y-0 ${
    type === "error" ? "bg-red-500" : type === "warning" ? "bg-yellow-500" : "bg-green-500"
  } text-white`;
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 3000);
}

// Global error handler
window.addEventListener('error', function(event) {
  console.error('Global error:', event.error);
  toast('An unexpected error occurred', 'error');
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(event) {
  console.error('Unhandled promise rejection:', event.reason);
  toast('An unexpected error occurred', 'error');
});

// Helper function to get current user ID
async function getCurrentUserId() {
  try {
    const profile = await api("/profile");
    return profile.auth_user_id || profile.user_id;
  } catch (error) {
    console.error("Failed to get current user ID:", error);
    return null;
  }
}

function setAuthView(loggedIn) {
  document.getElementById("auth-page").classList.toggle("hidden", loggedIn);
  document.getElementById("app-page").classList.toggle("hidden", !loggedIn);
}

function switchPage(pageName) {
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.querySelector(`.nav-btn[data-page="${pageName}"]`)?.classList.add("active");
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("visible"));
  document.getElementById(`page-${pageName}`)?.classList.add("visible");
}

function renderRows(containerId, rows, empty = "No data") {
  const el = document.getElementById(containerId);
  el.innerHTML = "";
  if (!rows || rows.length === 0) {
    el.innerHTML = `<p class="muted">${empty}</p>`;
    return;
  }
  rows.forEach((html) => {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = html;
    el.appendChild(row);
  });
}

async function markSettlement(path, splitId, successMessage) {
  try {
    await api(path, "POST", { split_id: splitId });
    toast(successMessage);
    await Promise.all([loadDashboard(), loadGroups()]);
  } catch (err) {
    toast(err.message);
  }
}

async function loadDashboard() {
  const dashboard = await api("/dashboard");
  document.getElementById("you-owe").textContent = `$${dashboard.you_owe || 0}`;
  document.getElementById("you-receive").textContent = `$${dashboard.you_receive || 0}`;
  document.getElementById("total-spent").textContent = `$${dashboard.total_spent || 0}`;

  // Load predictions
  await loadPredictions();
  
  // Load AI insights
  await loadAIInsights();
  
  // Load charts
  await loadCharts();

  // Category breakdown
  renderRows(
    "category-breakdown",
    (dashboard.category_breakdown || []).map((item) => `<span>${item.category}</span><strong>$${item.total}</strong>`),
    "No categorized expenses for this month",
  );

  renderRows(
    "trend-list",
    (dashboard.trends || []).map((t) => `<span>${t.period}</span><strong>$${t.amount}</strong>`),
    "No trends available",
  );

  renderRows(
    "alerts-list",
    (dashboard.alerts || []).map((a) => `<span class="alert">${a}</span>`),
    "No alerts",
  );

  const topCategory = dashboard.top_category;
  document.getElementById("top-category").innerHTML = topCategory
    ? `<span>${topCategory.category}</span><strong>$${topCategory.total}</strong>`
    : '<p class="muted">No top category available yet.</p>';

  renderRows(
    "recent-expenses",
    (dashboard.recent_transactions || []).map((r) => `<div class="flex justify-between items-center p-2 bg-gray-50 rounded"><span class="text-sm">${r.date} | ${r.category || "General"} | ${r.description || "-"}</span><span class="font-medium">$${r.amount}</span></div>`),
    "No expenses yet",
  );

  renderRows(
    "settlements-owe",
    (dashboard.settlements?.owe || []).map((s) => `<div class="flex justify-between items-center p-2 bg-red-50 rounded"><span class="text-sm">${s.from_name} owes ${s.to_name}</span><span class="font-medium text-red-600">$${s.amount}</span></div>`),
    "No amounts you owe",
  );

  renderRows(
    "settlements-receive",
    (dashboard.settlements?.receive || []).map((s) => `<div class="flex justify-between items-center p-2 bg-green-50 rounded"><span class="text-sm">${s.from_name} owes ${s.to_name}</span><span class="font-medium text-green-600">$${s.amount}</span></div>`),
    "No amounts owed to you",
  );

  renderRows(
    "group-settlements",
    dashboard.group_settlements || [],
    "No group settlements",
  );
}

async function loadPredictions() {
  try {
    const prediction = await api("/predictions/next-week");
    document.getElementById("predicted-total").textContent = `$${prediction.predicted_total}`;
    document.getElementById("predicted-change").textContent = `${prediction.percent_change > 0 ? '+' : ''}${prediction.percent_change}%`;
    document.getElementById("predicted-weeks").textContent = `${prediction.weeks_used} weeks`;
    
    // Add insight text
    const insightEl = document.getElementById("prediction-insight");
    if (prediction.percent_change > 10) {
      insightEl.textContent = "You are likely to spend more next week. Consider reviewing your budget.";
    } else if (prediction.percent_change < -10) {
      insightEl.textContent = "Great! Your spending is trending down. Keep it up!";
    } else {
      insightEl.textContent = "Your spending is expected to remain stable next week.";
    }
  } catch (error) {
    console.error("Failed to load predictions:", error);
  }
}

async function loadAIInsights() {
  try {
    const insights = await api("/ai/expense-insights");
    const container = document.getElementById("ai-insights");
    container.innerHTML = "";
    
    insights.insights.forEach((insight, index) => {
      const card = document.createElement("div");
      card.className = "bg-blue-50 border border-blue-200 rounded-lg p-4 fade-in";
      card.style.animationDelay = `${index * 0.1}s`;
      card.innerHTML = `
        <div class="flex items-start">
          <div class="text-blue-500 mr-3">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
            </svg>
          </div>
          <p class="text-sm text-gray-700">${insight}</p>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (error) {
    console.error("Failed to load AI insights:", error);
  }
}

async function loadCharts() {
  try {
    const expenses = await api("/expenses");
    
    // Category pie chart
    const categoryData = {};
    expenses.forEach(expense => {
      const category = expense.category || 'Other';
      categoryData[category] = (categoryData[category] || 0) + expense.amount;
    });

    const categoryCtx = document.getElementById('category-chart').getContext('2d');
    new Chart(categoryCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(categoryData),
        datasets: [{
          data: Object.values(categoryData),
          backgroundColor: [
            '#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'
          ],
          borderWidth: 3,
          borderColor: '#ffffff',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              padding: 15,
              font: {
                size: 12
              }
            }
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                const label = context.label || '';
                const value = '$' + context.parsed;
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((context.parsed / total) * 100).toFixed(1);
                return `${label}: ${value} (${percentage}%)`;
              }
            }
          }
        }
      }
    });

    // Weekly spending bar chart
    const weeklyData = {};
    expenses.forEach(expense => {
      const week = expense.date ? expense.date.substring(0, 7) : 'Unknown';
      weeklyData[week] = (weeklyData[week] || 0) + expense.amount;
    });

    const weeklyCtx = document.getElementById('weekly-chart').getContext('2d');
    new Chart(weeklyCtx, {
      type: 'bar',
      data: {
        labels: Object.keys(weeklyData).sort(),
        datasets: [{
          label: 'Weekly Spending',
          data: Object.keys(weeklyData).sort().map(week => weeklyData[week]),
          backgroundColor: '#3B82F6',
          borderColor: '#2563EB',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return '$' + value;
              }
            }
          }
        },
        plugins: {
          legend: {
            display: false
          }
        }
      }
    });
  } catch (error) {
    console.error("Failed to load charts:", error);
  }
}

async function loadGroups() {
  try {
    const response = await api("/groups");
    console.log("Groups API response:", response);
    
    const groupsListEl = document.getElementById("groups-list");
    groupsListEl.innerHTML = "";
    
    if (!response || response.length === 0) {
    groupsListEl.innerHTML = `
      <div class="text-center py-8">
        <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
          </svg>
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">Create your first group</h3>
        <p class="text-gray-500 text-sm">Start splitting expenses with friends and family</p>
      </div>
    `;
    return;
  }

  response.forEach((group) => {
    const groupCard = document.createElement("div");
    groupCard.className = "modern-card p-4 group-card";
    groupCard.innerHTML = `
      <div class="flex justify-between items-center">
        <div class="flex items-center space-x-3">
          <div class="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
            </svg>
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h4 class="font-semibold text-gray-800">${group.name}</h4>
              ${group.is_admin ? '<span class="admin-badge">Admin</span>' : ''}
            </div>
            <div class="flex items-center space-x-3 text-sm text-gray-500">
              <span>${group.member_count} members</span>
              <span>${group.is_admin ? 'You are admin' : 'Member'}</span>
            </div>
          </div>
        </div>
        <div class="flex space-x-2">
          <button class="view-group-btn text-blue-500 hover:text-blue-700 px-3 py-1 rounded-lg hover:bg-blue-50 transition-all text-sm font-medium" data-group-id="${group.group_id}">View</button>
          ${group.is_admin ? `<button class="delete-group-btn text-red-500 hover:text-red-700 px-3 py-1 rounded-lg hover:bg-red-50 transition-all text-sm font-medium" data-group-id="${group.group_id}">Delete</button>` : ''}
        </div>
      </div>
    `;
    groupsListEl.appendChild(groupCard);
  });

  // Add event listeners
  document.querySelectorAll(".view-group-btn").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      loadGroupDetails(btn.dataset.groupId);
    };
  });

  document.querySelectorAll(".delete-group-btn").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      if (confirm("Are you sure you want to delete this group? This will also delete all related expenses and splits.")) {
        deleteGroup(btn.dataset.groupId);
      }
    };
  });
  } catch (error) {
    console.error("Failed to load groups:", error);
    toast("Failed to load groups", "error");
  }
}

async function loadGroupDetails(groupId) {
  try {
    const [groupDetails, settlements, currentUserId] = await Promise.all([
      api(`/groups/${groupId}`),
      api(`/groups/${groupId}/settlements`),
      getCurrentUserId()
    ]);

    const detailsEl = document.getElementById("group-details");
    detailsEl.innerHTML = `
      <div class="space-y-6">
        <div>
          <h4 class="font-semibold text-gray-800 text-lg">${groupDetails.name || 'Unknown Group'}</h4>
          <p class="text-sm text-gray-500">Created by ${groupDetails.creator_name || 'Unknown'} · ${groupDetails.member_count || 0} members</p>
        </div>
        
        <div>
          <h5 class="font-medium text-gray-700 mb-4">Members</h5>
          <div id="group-members-list" class="space-y-3"></div>
        </div>
        
        <div>
          <h5 class="font-medium text-gray-700 mb-4">Pending Settlements</h5>
          <div id="settlements-list" class="space-y-3">
            ${(settlements.groups || []).flatMap(g => g.items).map(item => {
              const isReceiver = currentUserId == item.to_user_id;
              
              return `<div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div class="flex items-center space-x-3">
                  <img src="https://api.dicebear.com/8.x/bottts/svg?seed=${item.from_name}" alt="${item.from_name}" class="w-8 h-8 rounded-full">
                  <span class="text-sm font-medium">${item.from_name} owes ${item.to_name}</span>
                </div>
                <div class="flex items-center space-x-2">
                  <span class="font-bold text-red-600">$${item.amount}</span>
                  ${isReceiver ? 
                    `<button class="settle-btn bg-green-500 text-white px-3 py-1 rounded-lg hover:bg-green-600 transition-all text-sm" data-from="${item.from_user_id}" data-to="${item.to_user_id}" data-amount="${item.amount}" data-group="${groupId}">Settle</button>` :
                    `<span class="text-xs text-gray-400 px-3 py-1">Waiting for ${item.to_name}</span>`
                  }
                </div>
              </div>`;
            }).join('') || '<p class="text-gray-500 text-sm">No pending settlements</p>'}
          </div>
        </div>
      </div>
    `;

    // Load group members
    await loadGroupMembers(groupId);
  } catch (error) {
    console.error("Failed to load group details:", error);
    toast(error.message || "Failed to load group details", 'error');
  }
}

async function loadGroupMembers(groupId) {
  try {
    const response = await api("/groups");
    const group = response.data.groups.find(g => g.group_id == groupId);
    
    if (!group) return;

    // Get members from the group_members table
    const membersResponse = await api(`/groups/${groupId}/members`);
    const members = membersResponse.data.members || [];
    
    const membersListEl = document.getElementById("group-members-list");
    if (membersListEl) {
      if (members.length === 0) {
        membersListEl.innerHTML = '<p class="text-gray-500 text-sm">No members found</p>';
      } else {
        membersListEl.innerHTML = members.map(member => `
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div class="flex items-center space-x-3">
              <img src="https://api.dicebear.com/8.x/bottts/svg?seed=${member.username}" alt="${member.name}" class="w-10 h-10 rounded-full profile-avatar">
              <div>
                <p class="font-medium text-gray-800">${member.name || 'Unknown User'}</p>
                <p class="text-sm text-gray-500">@${member.username || 'unknown'}</p>
              </div>
            </div>
            ${group.is_admin ? `<button class="remove-member-btn text-red-500 hover:text-red-700 px-3 py-1 rounded-lg hover:bg-red-50 transition-all text-sm" data-user-id="${member.user_id}" data-group-id="${groupId}">Remove</button>` : ''}
          </div>
        `).join('');

        // Add event listeners for remove member buttons
        document.querySelectorAll(".remove-member-btn").forEach(btn => {
          btn.onclick = () => {
            const memberName = btn.closest('.bg-gray-50').querySelector('.font-medium').textContent;
            if (confirm(`Remove ${memberName} from the group?`)) {
              removeGroupMember(btn.dataset.groupId, btn.dataset.userId);
            }
          };
        });
      }
    }
  } catch (error) {
    console.error("Failed to load group members:", error);
    toast(error.message || "Failed to load group members", 'error');
  }

  // Add event listeners for settle buttons
  document.querySelectorAll(".settle-btn").forEach(btn => {
    btn.onclick = async () => {
      const fromId = btn.dataset.from;
      const toId = btn.dataset.to;
      const amount = parseFloat(btn.dataset.amount);
      const groupId = btn.dataset.group;
      
      if (confirm(`Settle payment of $${amount} from ${fromId} to ${toId}?`)) {
        try {
          const response = await api("/settle_payment", "POST", {
            from_user_id: parseInt(fromId),
            to_user_id: parseInt(toId),
            amount: amount,
            group_id: parseInt(groupId)
          });
          
          if (response.success) {
            toast(response.message || "Payment settled successfully");
            await loadGroupDetails(groupId);
            await loadDashboard(); // Update dashboard balances
          } else {
            toast(response.error || "Failed to settle payment", 'error');
          }
        } catch (error) {
          toast(error.message || "Failed to settle payment", 'error');
        }
      }
    };
  });
}

async function deleteGroup(groupId) {
  try {
    await api(`/groups/${groupId}`, "DELETE");
    toast("Group deleted successfully");
    await loadGroups();
  } catch (error) {
    toast(error.message);
  }
}

async function removeGroupMember(groupId, userId) {
  try {
    await api(`/groups/${groupId}/members/${userId}`, "DELETE");
    toast("Member removed successfully");
    await loadGroupDetails(groupId);
  } catch (error) {
    toast(error.message);
  }
}

async function loadFriends() {
  const [friends, requests] = await Promise.all([api("/friends"), api("/friends/requests")]);
  
  // Update friends list with action buttons
  const friendsListEl = document.getElementById("friends-list");
  friendsListEl.innerHTML = "";
  
  if (!friends.friends || friends.friends.length === 0) {
    friendsListEl.innerHTML = `
      <div class="text-center py-8">
        <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
          </svg>
        </div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">No friends yet</h3>
        <p class="text-gray-500 text-sm">Connect with friends to start splitting expenses together</p>
      </div>
    `;
  } else {
    friends.friends.forEach((friend) => {
      const friendCard = document.createElement("div");
      friendCard.className = "modern-card p-4 friend-card";
      friendCard.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <img src="https://api.dicebear.com/8.x/bottts/svg?seed=${friend.username}" alt="${friend.name}" class="w-10 h-10 rounded-full profile-avatar">
            <div>
              <p class="font-semibold text-gray-800">${friend.name}</p>
              <p class="text-sm text-gray-500">@${friend.username}</p>
            </div>
          </div>
          <div class="flex space-x-2">
            <button class="remove-friend-btn text-red-500 hover:text-red-700 px-3 py-1 rounded-lg hover:bg-red-50 transition-all text-sm font-medium" data-friend-id="${friend.auth_user_id}">Remove</button>
            <button class="block-friend-btn text-orange-500 hover:text-orange-700 px-3 py-1 rounded-lg hover:bg-orange-50 transition-all text-sm font-medium" data-friend-id="${friend.auth_user_id}">Block</button>
          </div>
        </div>
      `;
      friendsListEl.appendChild(friendCard);
    });
    
    // Add event listeners
    document.querySelectorAll(".remove-friend-btn").forEach(btn => {
      btn.onclick = () => {
        if (confirm("Are you sure you want to remove this friend?")) {
          removeFriend(btn.dataset.friendId);
        }
      };
    });
    
    document.querySelectorAll(".block-friend-btn").forEach(btn => {
      btn.onclick = () => {
        if (confirm("Are you sure you want to block this user?")) {
          blockFriend(btn.dataset.friendId);
        }
      };
    });
  }
  
  // Setup friend request functionality
  const searchInput = document.getElementById("friend-username");
  const sendButton = document.getElementById("send-friend-btn");
  
  sendButton.addEventListener("click", async () => {
    const username = searchInput.value.trim();
    if (!username) {
      toast("Please enter a username");
      return;
    }
    
    try {
      const response = await api("/friends/requests", "POST", { username });
      if (response.success) {
        toast(response.message || "Friend request sent successfully");
        searchInput.value = "";
        await loadFriends();
      } else {
        toast(response.error || "Failed to send friend request", "error");
      }
    } catch (error) {
      toast(error.message || "Failed to send friend request", "error");
    }
  });
  
  const incomingEl = document.getElementById("incoming-requests");
  incomingEl.innerHTML = "";
  if (!requests.incoming || requests.incoming.length === 0) {
    incomingEl.innerHTML = '<p class="text-gray-500 text-sm">No incoming requests</p>';
  } else {
    requests.incoming.forEach((request) => {
      const requestCard = document.createElement("div");
      requestCard.className = "modern-card p-4 friend-card";
      requestCard.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <img src="https://api.dicebear.com/8.x/bottts/svg?seed=${request.username}" alt="${request.username}" class="w-10 h-10 rounded-full profile-avatar">
            <div>
              <p class="font-semibold text-gray-800">@${request.username}</p>
              <p class="text-sm text-gray-500">Friend request</p>
            </div>
          </div>
          <div class="flex space-x-2">
            <button class="accept-btn bg-green-500 text-white px-3 py-1 rounded-lg hover:bg-green-600 transition-all text-sm font-medium" data-id="${request.request_id}">Accept</button>
            <button class="reject-btn bg-red-500 text-white px-3 py-1 rounded-lg hover:bg-red-600 transition-all text-sm font-medium" data-id="${request.request_id}">Reject</button>
          </div>
        </div>
      `;
      incomingEl.appendChild(requestCard);
    });
  }
  
  const outgoingEl = document.getElementById("outgoing-requests");
  outgoingEl.innerHTML = "";
  if (!requests.outgoing || requests.outgoing.length === 0) {
    outgoingEl.innerHTML = '<p class="text-gray-500 text-sm">No outgoing requests</p>';
  } else {
    requests.outgoing.forEach((request) => {
      const requestCard = document.createElement("div");
      requestCard.className = "modern-card p-4 friend-card";
      requestCard.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <img src="https://api.dicebear.com/8.x/bottts/svg?seed=${request.username}" alt="${request.username}" class="w-10 h-10 rounded-full profile-avatar">
            <div>
              <p class="font-semibold text-gray-800">@${request.username}</p>
              <p class="text-sm text-gray-500">Pending request</p>
            </div>
          </div>
          <span class="text-sm text-gray-500 px-3 py-1 bg-gray-100 rounded-lg">Pending</span>
        </div>
      `;
      outgoingEl.appendChild(requestCard);
    });
  }
  
  document.querySelectorAll(".accept-btn").forEach((btn) => {
    btn.onclick = async () => {
      await api("/friends/accept", "POST", { request_id: Number(btn.dataset.id) });
      toast("Request accepted");
      await loadFriends();
    };
  });
  
  document.querySelectorAll(".reject-btn").forEach((btn) => {
    btn.onclick = async () => {
      await api("/friends/reject", "POST", { request_id: Number(btn.dataset.id) });
      toast("Request rejected");
      await loadFriends();
    };
  });
}

async function removeFriend(friendId) {
  try {
    await api(`/friends/${friendId}`, "DELETE");
    toast("Friend removed successfully");
    await loadFriends();
  } catch (error) {
    toast(error.message);
  }
}

async function blockFriend(friendId) {
  try {
    await api("/friends/block", "POST", { friend_id: Number(friendId) });
    toast("User blocked successfully");
    await loadFriends();
  } catch (error) {
    toast(error.message);
  }
}

async function loadProfile() {
  const profile = await api("/profile");
  document.getElementById("profile-name").value = profile.name || "";
  document.getElementById("profile-username").value = profile.username || "";
  document.getElementById("profile-image").value = profile.profile_image || "";
  document.getElementById("profile-bio").value = profile.bio || "";
  
  // Update sidebar profile info
  document.getElementById("sidebar-profile-name").textContent = profile.name || "User";
  document.getElementById("sidebar-profile-username").textContent = "@" + (profile.username || "username");
  document.getElementById("sidebar-profile-image").src = profile.profile_image || "https://api.dicebear.com/8.x/bottts/svg?seed=smart-expense";
  
  // Update profile page display
  document.getElementById("profile-display-name").textContent = profile.name || "Your Name";
  document.getElementById("profile-display-username").textContent = "@" + (profile.username || "username");
  document.getElementById("profile-image-preview").src = profile.profile_image || "https://api.dicebear.com/8.x/bottts/svg?seed=smart-expense";
}

async function uploadProfileImage(file) {
  const formData = new FormData();
  formData.append('image', file);
  
  try {
    const response = await fetch('/profile/upload-image', {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || 'Upload failed');
    }
    
    toast(result.message);
    await loadProfile();
    return result.profile_image;
  } catch (error) {
    toast(error.message);
    throw error;
  }
}

async function loadExpenses() {
  const expenses = await api("/expenses");
  renderRows(
    "expenses-list",
    expenses.map((e) => `<span>${e.date} | ${e.category} | ${e.description}</span><strong>${e.amount}</strong>`),
    "No expenses yet"
  );
}

async function loadGroupsForExpense() {
  const response = await api("/groups");
  const select = document.getElementById("expense-group");
  select.innerHTML = '<option value="">Personal Expense</option>';
  (response.data?.groups || []).forEach((g) => {
    select.innerHTML += `<option value="${g.group_id}">${g.name}</option>`;
  });
}

async function addExpense() {
  const amount = parseFloat(document.getElementById("expense-amount").value);
  const description = document.getElementById("expense-description").value;
  const category = document.getElementById("expense-category").value;
  const date = document.getElementById("expense-date").value;
  const groupId = document.getElementById("expense-group").value;
  const splitType = document.querySelector('input[name="split-type"]:checked').value;
  
  if (!amount || !description) {
    toast("Please fill in amount and description");
    return;
  }

  const currentUser = await api("/profile");
  const paidBy = currentUser.user_id;
  
  const payload = {
    amount,
    paid_by: paidBy,
    description,
    category,
    date: date || new Date().toISOString().split('T')[0],
    group_id: groupId ? parseInt(groupId) : null
  };

  if (splitType === "equal") {
    // For equal split, API will handle splitting among group members if group is selected
    if (!groupId) {
      toast("Please select a group for equal split");
      return;
    }
  } else {
    // Custom split logic would go here
    toast("Custom split not implemented yet");
    return;
  }

  try {
    const response = await api("/expenses", "POST", payload);
    if (response.success) {
      toast(response.message || "Expense added successfully");
      document.getElementById("expense-amount").value = "";
      document.getElementById("expense-description").value = "";
      document.getElementById("expense-date").value = "";
      await loadExpenses(); // Refresh expenses list
      await loadDashboard(); // Refresh dashboard to show updated totals
    } else {
      toast(response.error || "Failed to add expense", 'error');
    }
  } catch (error) {
    toast(error.message || "Failed to add expense", 'error');
  }
}

async function bootLoggedIn() {
  setAuthView(true);
  switchPage("dashboard");
  await Promise.all([loadDashboard(), loadGroups(), loadFriends(), loadProfile()]);
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("tab-login").onclick = () => {
    document.getElementById("tab-login").classList.add("active");
    document.getElementById("tab-register").classList.remove("active");
    document.getElementById("login-form").classList.remove("hidden");
    document.getElementById("register-form").classList.add("hidden");
  };
  document.getElementById("tab-register").onclick = () => {
    document.getElementById("tab-register").classList.add("active");
    document.getElementById("tab-login").classList.remove("active");
    document.getElementById("register-form").classList.remove("hidden");
    document.getElementById("login-form").classList.add("hidden");
  };

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.onclick = async () => {
      const page = btn.dataset.page;
      switchPage(page);
      if (page === "dashboard") await loadDashboard();
      if (page === "expenses") {
        await Promise.all([loadExpenses(), loadGroupsForExpense()]);
      }
      if (page === "groups") await loadGroups();
      if (page === "friends") await loadFriends();
      if (page === "profile") await loadProfile();
    };
  });

  document.getElementById("register-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/auth/register", "POST", {
        name: document.getElementById("register-name").value.trim(),
        username: document.getElementById("register-username").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
      });
      toast("Registration successful");
      document.getElementById("tab-login").click();
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/auth/login", "POST", {
        identifier: document.getElementById("login-identifier").value.trim(),
        password: document.getElementById("login-password").value,
      });
      await bootLoggedIn();
      toast("Logged in");
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("logout-btn").onclick = async () => {
    await api("/auth/logout", "POST");
    setAuthView(false);
    toast("Logged out");
  };

  document.getElementById("send-friend-btn").onclick = async () => {
    const username = selectedUsername || document.getElementById("friend-username").value.trim();
    if (!username) {
      toast("Please enter or select a username");
      return;
    }
    try {
      const response = await api("/friends/request", "POST", { username });
      if (response.success) {
        toast(response.message || "Friend request sent successfully");
        await loadFriends(); // Immediately refresh friends list
        document.getElementById("friend-username").value = "";
        selectedUsername = null;
        document.getElementById("send-friend-btn").disabled = true;
      } else {
        toast(response.error || "Failed to send friend request", 'error');
      }
    } catch (error) {
      toast(error.message || "Failed to send friend request", 'error');
    }
  };

  document.getElementById("create-group-btn").onclick = async () => {
    const name = document.getElementById("group-name").value.trim();
    const member_usernames = document
      .getElementById("group-members")
      .value.split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    
    console.log("Creating group:", { name, member_usernames });
    
    try {
      const response = await api("/groups", "POST", { name, member_usernames });
      console.log("Group creation response:", response);
      
      if (response.success) {
        document.getElementById("group-name").value = "";
        document.getElementById("group-members").value = "";
        await loadGroups(); // Immediately refresh groups list
        toast("Group created successfully");
      } else {
        console.error("Backend error:", response.error);
        toast(response.error || "Failed to create group", 'error');
      }
    } catch (err) {
      console.error("Group creation error:", err);
      toast(err.message || "Failed to create group", 'error');
    }
  };

  document.getElementById("profile-save-btn").onclick = async () => {
    try {
      await api("/profile/update", "POST", {
        name: document.getElementById("profile-name").value.trim(),
        profile_image: document.getElementById("profile-image").value.trim(),
      });
      toast("Profile updated");
      await loadProfile();
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("profile-dropdown-btn").onclick = () => {
    const dropdown = document.getElementById("profile-dropdown");
    dropdown.classList.toggle("hidden");
  };

  document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("profile-dropdown");
    const dropdownBtn = document.getElementById("profile-dropdown-btn");
    if (!dropdownBtn.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.add("hidden");
    }
  });

  document.getElementById("edit-profile-btn").onclick = () => {
    document.getElementById("profile-dropdown").classList.add("hidden");
    switchPage("profile");
    loadProfile();
  };

  document.getElementById("profile-image-upload").onchange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      try {
        await uploadProfileImage(file);
      } catch (error) {
        // Error handled in uploadProfileImage function
      }
    }
  };

  const originalProfileSaveBtn = document.getElementById("profile-save-btn");
  if (originalProfileSaveBtn) {
    originalProfileSaveBtn.onclick = async () => {
      try {
        await api("/profile/update", "POST", {
          name: document.getElementById("profile-name").value.trim(),
          bio: document.getElementById("profile-bio").value.trim(),
          profile_image: document.getElementById("profile-image").value.trim(),
        });
        toast("Profile updated");
        await loadProfile();
      } catch (err) {
        toast(err.message);
      }
    };
  }

  document.getElementById("add-expense-btn").onclick = addExpense;

  api("/auth/me")
    .then(() => bootLoggedIn())
    .catch(() => setAuthView(false));
});
