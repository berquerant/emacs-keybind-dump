;;; keybind-dump.el --- Dump keybindings to JSONL -*- lexical-binding: t -*-

;;; Commentary:

;; Dumps keybindings registered across Emacs keymaps to JSONL (one JSON object per line).
;; Based on and extending /Users/sin/tmp/my-keybind-dump.el.

;;; Code:

(require 'json)
(require 'seq)
(require 'subr-x)
(require 'cl-lib)

(defun keybind-dump--extract-keymap (map-name keymap)
  "Extract leaf bindings from KEYMAP named MAP-NAME."
  (let ((items nil)
        (visited-maps nil))
    (cl-labels ((walk (km prefix-vec)
                  (let ((actual (if (symbolp km)
                                    (and (boundp km) (symbol-value km))
                                  km)))
                    (when (and actual (keymapp actual) (not (memq actual visited-maps)))
                      (push actual visited-maps)
                      (map-keymap
                       (lambda (event binding)
                         (let ((full-vec (vconcat prefix-vec (vector event))))
                           (cond
                            ((keymapp binding)
                             (when (< (length prefix-vec) 8)
                               (walk binding full-vec)))
                            ((and binding (not (numberp binding)))
                             (let ((seq (key-description full-vec))
                                   (cmd (cond
                                         ((symbolp binding) (symbol-name binding))
                                         ((stringp binding) binding)
                                         (t (format "%s" binding)))))
                               (push `((sequence . ,seq)
                                       (keymap . ,map-name)
                                       (command . ,cmd))
                                     items))))))
                       actual)))))
      (walk keymap []))
    (nreverse items)))

(defun keybind-dump-all-keymaps ()
  "Collect keybindings from `global-map' and all known *-map / *-mode-map keymaps."
  (let ((map-entries nil)
        (result nil))
    (push (cons "global-map" (current-global-map)) map-entries)
    (mapatoms
     (lambda (sym)
       (when (and (boundp sym)
                  (not (memq sym '(global-map current-global-map global-override-map)))
                  (keymapp (symbol-value sym))
                  (string-match-p "\\(-map\\|-mode-map\\)$" (symbol-name sym)))
         (push (cons (symbol-name sym) (symbol-value sym)) map-entries))))
    (setq map-entries (sort map-entries (lambda (a b) (string< (car a) (car b)))))
    (dolist (entry map-entries)
      (let ((extracted (keybind-dump--extract-keymap (car entry) (cdr entry))))
        (setq result (nconc result extracted))))
    result))

(defun keybind-dump-jsonl ()
  "Dump all keybindings to stdout as JSON Lines."
  (let ((entries (keybind-dump-all-keymaps)))
    (dolist (item entries)
      (princ (json-encode item))
      (princ "\n"))))

(provide 'keybind-dump)
;;; keybind-dump.el ends here
