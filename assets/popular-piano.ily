%% popular-piano.ily — house style for readable piano-solo sheets (include from a score .ly)
%% Style anchors: commercial piano-solo transcriptions (title block, chord symbols above the
%% grand staff, tempo word + metronome, 4–5 systems per A4 page, 3–5 bars per system, bar numbers
%% at the start of each system, 8va lines instead of ledger towers, "with pedal" once).
\version "2.26.0"

\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm
  bottom-margin = 12\mm
  left-margin = 14\mm
  right-margin = 14\mm
  ragged-bottom = ##f
  ragged-last-bottom = ##t
  max-systems-per-page = 5
  system-system-spacing.basic-distance = #17
  system-system-spacing.padding = #3
  markup-system-spacing.padding = #4
  top-markup-spacing.basic-distance = #8
  print-page-number = ##t
  print-first-page-number = ##t
  oddHeaderMarkup = \markup \null
  evenHeaderMarkup = \markup \null
  oddFooterMarkup = \markup \fill-line { \fontsize #-1 \fromproperty #'page:page-number-string }
  evenFooterMarkup = \oddFooterMarkup
  bookTitleMarkup = \markup {
    \column {
      \fill-line { \fontsize #6 \bold \fromproperty #'header:title }
      \fill-line { \fontsize #1 \fromproperty #'header:subtitle }
      \fill-line { \fontsize #0 \fromproperty #'header:subsubtitle }
      \vspace #0.4
      \fill-line { \null \fontsize #-1 \fromproperty #'header:composer }
      \fill-line { \null \fontsize #-1 \fromproperty #'header:arranger }
    }
  }
}

#(set-global-staff-size 19)

\layout {
  \context {
    \Score
    \override BarNumber.break-visibility = #begin-of-line-visible
    \override BarNumber.self-alignment-X = #LEFT
    \override BarNumber.font-size = #-1
    \override BarNumber.padding = #1
    \override MetronomeMark.font-size = #-1
    \override SpacingSpanner.common-shortest-duration = #(ly:make-moment 1/8)
    \override RehearsalMark.self-alignment-X = #LEFT
    \accidentalStyle modern
  }
  \context {
    \Staff
    \accidentalStyle modern
    \override TimeSignature.style = #'numbered
  }
  \context {
    \ChordNames
    \override ChordName.font-size = #-1
    chordChanges = ##t
    majorSevenSymbol = \markup { "maj7" }
  }
  \context {
    \PianoStaff
    \accidentalStyle modern   % PianoStaff's built-in "piano" style would otherwise win over Score
    \override VerticalAxisGroup.staff-staff-spacing.basic-distance = #10
    \override VerticalAxisGroup.staff-staff-spacing.padding = #2
  }
}

%% ---- shorthands the engraver may use ------------------------------------
withPedal = _\markup { \italic "with pedal" }   % below the note it is attached to (put it on the first LH note)
ottavaOn  = { \ottava #1 }
ottavaBassa = { \ottava #-1 }
ottavaOff = { \ottava #0 }
%% tempo word + metronome in one:  \tempoWord "Moderately" 76
tempoWord =
#(define-music-function (word bpm) (string? number?)
   #{ \tempo \markup { \bold #word } 4 = #bpm #})
%% compound metres / other referents:  \tempoWordDur "Andante" 4. 44
tempoWordDur =
#(define-music-function (word dur bpm) (string? ly:duration? number?)
   #{ \tempo \markup { \bold #word } $dur = #bpm #})
