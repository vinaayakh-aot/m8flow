import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function TemplateDeleteConfirmDialog({
  open,
  templateName,
  isPublished,
  submitting,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  templateName: string;
  isPublished: boolean;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const description = isPublished
    ? `"${templateName}" will be soft-deleted and can be restored from the Deleted tab.`
    : `"${templateName}" will be permanently deleted.`;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onCancel(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete template?</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={submitting}>
            {submitting ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TemplateRestoreConfirmDialog({
  open,
  templateName,
  submitting,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  templateName: string;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onCancel(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Restore template?</DialogTitle>
          <DialogDescription>
            {`"${templateName}" will be restored and become active again.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm} disabled={submitting}>
            {submitting ? 'Restoring…' : 'Restore'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
