document.addEventListener('DOMContentLoaded', function () {
  // Player card expand/collapse
  document.querySelectorAll('[data-toggle-player]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var card = btn.closest('.player-card');
      card.classList.toggle('open');
    });
  });

  // Flash auto-dismiss
  document.querySelectorAll('.flash').forEach(function (el) {
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transition = 'opacity 0.3s';
      setTimeout(function () { el.remove(); }, 300);
    }, 4000);
  });

  // Confirm modal
  window.showConfirm = function (id) {
    document.getElementById(id).classList.remove('hidden');
  };

  window.hideConfirm = function (id) {
    document.getElementById(id).classList.add('hidden');
  };
});

function togglePlayerCard(el) {
  var card = el.closest('.player-card');
  card.classList.toggle('open');
}
