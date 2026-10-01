import subprocess
import json
import re

# Clean script without any blank lines (\n\n)
clean_script = """<script>
(function() {
  function initCalc() {
    var wageInput = document.getElementById('inputHourlyWage');
    var hoursInput = document.getElementById('inputWeeklyHours');
    var wageError = document.getElementById('wageErrorMsg');
    var hoursError = document.getElementById('hoursErrorMsg');
    var badge = document.getElementById('resBadge');
    var basicWeekly = document.getElementById('resBasicWeekly');
    var holidayWeekly = document.getElementById('resHolidayWeekly');
    var totalWeekly = document.getElementById('resTotalWeekly');
    var monthlyWage = document.getElementById('resMonthlyWage');
    var monthlyHours = document.getElementById('resMonthlyHours');
    var netMonthly = document.getElementById('resNetMonthly');
    var presets = document.querySelectorAll('#calcPresets button');
    if (!wageInput || !hoursInput) return;
    function formatNumber(num) {
      return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
    }
    function syncPresets(currentHours) {
      presets.forEach(function(b) {
        var h = parseFloat(b.getAttribute('data-hours'));
        if (!isNaN(currentHours) && h === currentHours) {
          b.style.background = '#e6f4ea';
          b.style.color = '#0d7d59';
          b.style.borderColor = '#0d7d59';
          b.style.fontWeight = '700';
        } else {
          b.style.background = '#f8fafc';
          b.style.color = '#334155';
          b.style.borderColor = '#cbd5e1';
          b.style.fontWeight = '600';
        }
      });
    }
    function calculate() {
      var wage = parseFloat(wageInput.value);
      var hours = parseFloat(hoursInput.value);
      syncPresets(hours);
      var valid = true;
      if (isNaN(wage) || wage < 10700 || wage > 50000) {
        if (wageError) wageError.style.display = 'block';
        valid = false;
      } else {
        if (wageError) wageError.style.display = 'none';
      }
      if (isNaN(hours) || hours < 1 || hours > 52) {
        if (hoursError) hoursError.style.display = 'block';
        valid = false;
      } else {
        if (hoursError) hoursError.style.display = 'none';
      }
      if (!valid) return;
      var holidayH = 0;
      if (hours < 15) {
        holidayH = 0;
        if (badge) {
          badge.textContent = '주 15시간 미만 (주휴수당 미적용)';
          badge.style.background = '#fef3c7';
          badge.style.color = '#92400e';
        }
      } else {
        if (hours >= 40) {
          holidayH = 8.0;
        } else {
          holidayH = (hours / 40.0) * 8.0;
        }
        if (badge) {
          badge.textContent = '주휴수당 적용 대상 (주 ' + holidayH.toFixed(1) + '시간 인정)';
          badge.style.background = '#d1fae5';
          badge.style.color = '#065f46';
        }
      }
      var basicW = Math.round(hours * wage);
      var holidayW = Math.round(holidayH * wage);
      var totalW = basicW + holidayW;
      var mHours = 0;
      if (hours === 40) {
        mHours = 209;
      } else {
        mHours = Math.round((hours + holidayH) * (365.0 / 7.0 / 12.0));
      }
      var mWage = mHours * wage;
      var netEstimate = mWage;
      if (hours >= 15) {
        netEstimate = Math.round(mWage * (1 - 0.094));
      }
      if (basicWeekly) basicWeekly.textContent = formatNumber(basicW) + '원';
      if (holidayWeekly) holidayWeekly.textContent = formatNumber(holidayW) + '원';
      if (totalWeekly) totalWeekly.textContent = formatNumber(totalW) + '원';
      if (monthlyWage) monthlyWage.textContent = formatNumber(mWage) + '원';
      if (monthlyHours) monthlyHours.textContent = '(월 ' + mHours + '시간)';
      if (netMonthly) netMonthly.textContent = '약 ' + formatNumber(netEstimate) + '원';
    }
    presets.forEach(function(btn) {
      btn.addEventListener('click', function() {
        hoursInput.value = btn.getAttribute('data-hours');
        calculate();
      });
    });
    wageInput.addEventListener('input', calculate);
    wageInput.addEventListener('change', calculate);
    hoursInput.addEventListener('input', calculate);
    hoursInput.addEventListener('change', calculate);
    hoursInput.addEventListener('keyup', calculate);
    calculate();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCalc);
  } else {
    initCalc();
  }
})();
</script>"""

# Check for consecutive newlines
assert "\n\n" not in clean_script, "clean_script must not have consecutive newlines"
print("SUCCESS: clean_script has zero double newlines.")
