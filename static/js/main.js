// Auto-dismiss alerts after 4 seconds
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
    if (bsAlert) bsAlert.close();
  }, 4000);
});

// Prevent same hub selection in shipment form
const originSelect = document.querySelector('select[name="origin_hub"]');
const destSelect   = document.querySelector('select[name="destination_hub"]');

function syncHubSelects() {
  if (!originSelect || !destSelect) return;
  const originVal = originSelect.value;
  const destVal   = destSelect.value;
  if (originVal && destVal && originVal === destVal) {
    destSelect.value = '';
  }
}

if (originSelect) originSelect.addEventListener('change', syncHubSelects);
if (destSelect)   destSelect.addEventListener('change', syncHubSelects);
