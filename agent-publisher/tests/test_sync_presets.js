// Simulation test for preset synchronization logic
class MockElement {
  constructor(attrs = {}) {
    this.attrs = attrs;
    this.style = {};
    this.value = attrs.value || '';
  }
  getAttribute(name) {
    return this.attrs[name];
  }
}

const presets = [
  new MockElement({'data-hours': '14'}),
  new MockElement({'data-hours': '15'}),
  new MockElement({'data-hours': '20'}),
  new MockElement({'data-hours': '30'}),
  new MockElement({'data-hours': '40'}),
];

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

function getActivePreset() {
  const active = presets.filter(b => b.style.fontWeight === '700');
  return active.map(b => b.getAttribute('data-hours'));
}

// 1. Initial 40h -> button 40 active
syncPresets(40);
console.log('Hours 40: active presets =', getActivePreset());
if (getActivePreset().join(',') !== '40') throw new Error('Failed at 40');

// 2. Select 20h -> button 20 active
syncPresets(20);
console.log('Hours 20: active presets =', getActivePreset());
if (getActivePreset().join(',') !== '20') throw new Error('Failed at 20');

// 3. User types 25 in input -> ALL buttons inactive!
syncPresets(25);
console.log('Hours 25: active presets =', getActivePreset());
if (getActivePreset().length !== 0) throw new Error('Failed: 25 should have NO active preset!');

// 4. User types 14 in input -> button 14 active!
syncPresets(14);
console.log('Hours 14: active presets =', getActivePreset());
if (getActivePreset().join(',') !== '14') throw new Error('Failed at 14');

// 5. User types NaN or empty -> ALL buttons inactive!
syncPresets(NaN);
console.log('Hours NaN: active presets =', getActivePreset());
if (getActivePreset().length !== 0) throw new Error('Failed: NaN should have NO active preset!');

console.log('ALL PRESET SYNC TESTS PASSED SUCCESSFULLY!');
